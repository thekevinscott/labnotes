import asyncio
import gc
import json
import socket
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

import pytest
import uvicorn
from dirsql import DirSQL

from labnotes.daemon.server import ExperimentDaemon
from labnotes.read_config import read_config
from labnotes.tables.open_experiment_tables import open_experiment_tables

RUN = "20261114-000001-quiet-pond"
ROUTES = [
    "/runs",
    f"/runs/{RUN}/files",
    f"/runs/{RUN}/files/stdout.log",
    f"/runs/{RUN}/files/image.png",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "exp/runs" / RUN
    folder.mkdir(parents=True)
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "true"\n'
    )
    (folder / "run.json").write_text(
        json.dumps({"params": {}, "created": "2026-11-14T00:00:01Z"})
    )
    (folder / "stdout.log").write_text("starting\n")
    (folder / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\0")
    return tmp_path


@pytest.fixture
def sock() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-") as folder:
        yield Path(folder) / "d.sock"


@asynccontextmanager
async def daemon(
    root: Path, sock: Path, spy: Callable[[Any], None]
) -> AsyncIterator[DirSQL]:
    config = read_config(root / ".labnotes.toml")
    tables = open_experiment_tables(config, "exp")
    watch = tables.watch

    def watched() -> Any:
        changes = watch()
        spy(changes)
        return changes

    tables.watch = watched  # type: ignore[method-assign]
    app = ExperimentDaemon(config, "exp", tables)
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(sock))
    listener.listen()
    server = uvicorn.Server(
        uvicorn.Config(app, lifespan="off", log_config=None, access_log=False)
    )
    server.config.load()
    server.lifespan = server.config.lifespan_class(server.config)
    await server.startup(sockets=[listener])
    try:
        await tables.ready()
        yield tables
    finally:
        await server.shutdown()


async def visit(sock: Path, route: str) -> None:
    """Read the route's first event, then hang up."""
    reader, writer = await asyncio.open_unix_connection(str(sock))
    writer.write(f"GET {route} HTTP/1.1\r\nHost: labnotes\r\n\r\n".encode())
    await writer.drain()
    received = b""
    while b"\n\n" not in received.partition(b"event:")[2]:
        chunk = await asyncio.wait_for(reader.read(4096), 10)
        assert chunk, received
        received += chunk
    writer.close()
    await writer.wait_closed()


async def eventually(check: Callable[[], bool]) -> None:
    for _ in range(100):
        if check():
            return
        await asyncio.sleep(0.05)
    assert check()


@pytest.mark.parametrize("route", ROUTES)
def test_a_client_that_hangs_up_closes_its_watch_stream(
    root: Path, sock: Path, route: str
) -> None:
    streams: list[Any] = []

    def spy(changes: Any) -> None:
        changes.aclose = mock.AsyncMock()
        streams.append(changes)

    async def scenario() -> None:
        async with daemon(root, sock, spy):
            await visit(sock, route)
            await eventually(
                lambda: bool(streams) and streams[0].aclose.await_count == 1
            )

    asyncio.run(scenario())

    [changes] = streams
    changes.aclose.assert_awaited_once_with()


@pytest.mark.xfail(reason="dirsql watch streams have no aclose yet", strict=True)
@pytest.mark.parametrize("route", ROUTES)
def test_the_daemon_holds_no_stream_once_its_client_hangs_up(
    root: Path, sock: Path, route: str
) -> None:
    async def scenario() -> None:
        async with daemon(root, sock, lambda _: None) as tables:
            await visit(sock, route)
            streams = tables._watch_streams  # type: ignore[attr-defined]
            await eventually(lambda: not streams)

    gc.disable()
    try:
        asyncio.run(scenario())
    finally:
        gc.enable()
