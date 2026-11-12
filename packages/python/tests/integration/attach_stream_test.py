import asyncio
import fcntl
import json
import os
import socket
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

from labnotes.daemon.socket_path import lock_path, socket_path, socket_record
from labnotes.models import LabnotesConfig
from labnotes.read_config import read_config
from labnotes.tui.run_app import RunApp

STREAM_LIMIT = 16 * 1024 * 1024
ACCEPTED = b'{"ok":true,"journals":["j"]}\n'
Daemon = Callable[..., Callable[[], list[bytes]]]


@pytest.fixture
def config(tmp_path: Path) -> Iterator[LabnotesConfig]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": folder}):
            (tmp_path / ".labnotes.toml").write_text("")
            yield read_config(tmp_path / ".labnotes.toml")


@pytest.fixture
def daemon(config: LabnotesConfig) -> Iterator[Daemon]:
    """Hold the daemon lock and answer one attach with fixed bytes."""
    path = socket_path(config, "exp")
    record = socket_record(config, "exp")
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(str(path))
    threads: list[threading.Thread] = []
    # The server thread may see the close long after the client leaves.
    lagging = threading.Event()
    with (
        lock_path(config, "exp").open("a+b") as held,
        socket.socket(socket.AF_UNIX) as server,
    ):
        fcntl.flock(held, fcntl.LOCK_EX)
        server.bind(str(path))
        server.listen(1)

        def start(
            *lines: bytes, reply: bytes = ACCEPTED, until_closed: bool = False
        ) -> Callable[[], list[bytes]]:
            received: list[bytes] = []

            def serve() -> None:
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(10)
                    received.append(connection.makefile("rb").readline())
                    connection.sendall(reply + b"".join(lines))
                    if until_closed and connection.recv(1) == b"":
                        lagging.wait(10)
                        received.append(b"closed")

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            threads.append(thread)

            def served() -> list[bytes]:
                lagging.set()
                thread.join(timeout=10)
                return received

            return served

        yield start
        lagging.set()
        for thread in threads:
            thread.join(timeout=10)


def planned(run: str, size: int | None = None) -> bytes:
    event = {
        "event": "planned",
        "title": "exp",
        "runs": [{"run": run, "params": {}}],
        "concurrency": 1,
    }
    line = json.dumps({"journal": "j", "event": {**event, "pad": ""}})
    if size is not None:
        line = line.replace('"pad": ""', '"pad": "' + "x" * (size - len(line)) + '"')
        assert len(line) == size
    return line.encode() + b"\n"


def attached(config: LabnotesConfig) -> RunApp:
    app = RunApp(None, "exp", ("run", "params", "status", "time"), config, attach=True)

    async def drive() -> None:
        async with app.run_test() as pilot:
            for _ in range(100):
                if app.disconnected or not app.is_running:
                    break
                await pilot.pause(0.05)

    asyncio.run(drive())
    return app


def test_events_sent_with_the_attach_reply_are_not_lost(
    config: LabnotesConfig, daemon: Daemon
) -> None:
    served = daemon(planned("r1"), planned("r2"))
    app = attached(config)
    assert served() == [b'{"command":"attach"}\n']
    assert app.disconnected
    assert list(app.body.cells) == ["r1", "r2"]


def test_stream_accepts_events_up_to_sixteen_mebibytes(
    config: LabnotesConfig, daemon: Daemon
) -> None:
    daemon(
        planned("fits", STREAM_LIMIT),
        planned("too big", STREAM_LIMIT + 1),
        planned("after"),
    )
    app = attached(config)
    assert app.disconnected
    assert list(app.body.cells) == ["fits"]


def test_leaving_closes_the_attach_connection(
    config: LabnotesConfig, daemon: Daemon
) -> None:
    served = daemon(until_closed=True)
    app = RunApp(None, "exp", ("run",), config, attach=True)

    async def drive() -> None:
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            assert app.attached is not None

    asyncio.run(drive())
    assert served() == [b'{"command":"attach"}\n', b"closed"]


def test_a_rejected_attach_reports_the_error_and_closes(
    config: LabnotesConfig, daemon: Daemon
) -> None:
    served = daemon(reply=b'{"ok":false,"error":"busy"}\n', until_closed=True)
    app = attached(config)
    assert str(app.error) == "busy"
    assert served() == [b'{"command":"attach"}\n', b"closed"]
