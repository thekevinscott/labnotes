import json
import socket
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from labnotes.daemon.command import command


def test_start_waits_for_slow_daemon_reply_without_losing_discovery() -> None:
    with (
        TemporaryDirectory(prefix="ln-slow-") as folder,
        socket.socket(socket.AF_UNIX) as server,
    ):
        path = Path(folder) / "daemon.sock"
        record = Path(folder) / "daemon.socket"
        record.write_text(str(path))
        server.bind(str(path))
        server.listen(1)

        def respond() -> None:
            connection, _ = server.accept()
            with connection:
                with connection.makefile("r") as requests:
                    assert json.loads(requests.readline())["command"] == "start"
                time.sleep(10.5)
                try:
                    connection.sendall(b'{"ok":true,"journal":"running.jsonl"}\n')
                except BrokenPipeError:
                    pass  # The old client closes before the delayed reply.

        worker = threading.Thread(target=respond, daemon=True)
        worker.start()
        try:
            with (
                mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
                mock.patch(
                    "labnotes.daemon.command.socket_record", return_value=record
                ),
            ):
                assert command(mock.Mock(), "exp", {"command": "start"}) == {
                    "ok": True,
                    "journal": "running.jsonl",
                }
            assert path.exists()
            assert record.exists()
        finally:
            worker.join(timeout=15)
            assert not worker.is_alive()
