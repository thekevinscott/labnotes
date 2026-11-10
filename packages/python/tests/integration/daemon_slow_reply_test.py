import fcntl
import json
import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

from labnotes.daemon.command import command
from labnotes.daemon.socket_path import lock_path, socket_path, socket_record
from labnotes.read_config import read_config


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": folder}):
            yield Path(folder)


@pytest.mark.parametrize("action", ["start", "restart"])
def test_start_waits_for_slow_daemon_reply_without_losing_discovery(
    tmp_path: Path, runtime: Path, action: str
) -> None:
    config_path = tmp_path / ".labnotes.toml"
    config_path.write_text("")
    config = read_config(config_path)
    path = socket_path(config, "exp")
    assert path.is_relative_to(runtime)
    record = socket_record(config, "exp")
    lock = lock_path(config, "exp")
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(str(path))

    with lock.open("a+b") as held, socket.socket(socket.AF_UNIX) as server:
        fcntl.flock(held, fcntl.LOCK_EX)
        server.bind(str(path))
        server.listen(1)

        def respond() -> None:
            connection, _ = server.accept()
            with connection:
                with connection.makefile("r") as requests:
                    assert json.loads(requests.readline())["command"] == action
                time.sleep(10.5)
                try:
                    connection.sendall(b'{"ok":true,"journal":"running.jsonl"}\n')
                except BrokenPipeError:
                    pass  # The old client closes before the delayed reply.

        worker = threading.Thread(target=respond, daemon=True)
        worker.start()
        try:
            assert command(config, "exp", {"command": action}) == {
                "ok": True,
                "journal": "running.jsonl",
            }
            assert path.exists()
            assert record.exists()
        finally:
            worker.join(timeout=15)
            assert not worker.is_alive()
