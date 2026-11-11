import asyncio
import json
import socket
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.run_app import RunApp

COLUMNS = ("run", "params", "status", "time")


STREAM_LIMIT = 16 * 1024 * 1024


def envelope(note: str, size: int | None = None) -> bytes:
    line = json.dumps({"journal": "j", "event": {"event": note, "pad": ""}})
    if size is not None:
        line = line.replace('"pad": ""', '"pad": "' + "x" * (size - len(line)) + '"')
        assert len(line) == size
    return line.encode() + b"\n"


ACCEPTED = b'{"ok":true,"journals":["j"]}\n'


def daemon_sending(
    *lines: bytes, reply: bytes = ACCEPTED
) -> Iterator[tuple[Path, list[bytes]]]:
    with tempfile.TemporaryDirectory(dir="/tmp") as folder:
        path = Path(folder) / "d.sock"
        server = socket.socket(socket.AF_UNIX)
        server.bind(str(path))
        server.listen(1)
        received: list[bytes] = []

        def serve() -> None:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(10)
                received.append(connection.makefile("rb").readline())
                connection.sendall(reply + b"".join(lines))
                if reply != ACCEPTED and connection.recv(1) == b"":
                    received.append(b"closed")

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        yield path, received
        thread.join(timeout=10)
        server.close()


def streamed_notes(*lines: bytes) -> list[str]:
    config = mock.Mock(
        root=Path("/nonexistent"), experiments="{experiment}", defaults={}
    )
    app = RunApp(None, "exp", COLUMNS, config)
    notes: list[str] = []
    for path, received in daemon_sending(*lines):
        with (
            mock.patch("labnotes.tui.run_app.daemon_socket", return_value=path),
            mock.patch.object(app, "query_one"),
            mock.patch.object(
                app, "forward", side_effect=lambda j, e: notes.append(e["event"])
            ),
        ):
            assert app.attach_daemon() == ["j"]
            asyncio.run(app.read_stream())
        assert received == [b'{"command":"attach"}\n']
    assert app.disconnected
    return notes


def test_events_sent_with_the_attach_reply_are_not_lost() -> None:
    assert streamed_notes(envelope("first"), envelope("second")) == [
        "first",
        "second",
    ]


def test_stream_accepts_events_up_to_sixteen_mebibytes() -> None:
    assert streamed_notes(
        envelope("fits", STREAM_LIMIT),
        envelope("too big", STREAM_LIMIT + 1),
        envelope("after"),
    ) == ["fits"]


def test_detached_attach_replies_and_closes(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    for path, received in daemon_sending(
        reply=b'{"ok":true,"journals":["/j1","/j2"]}\n'
    ):
        with mock.patch("labnotes.tui.run_app.daemon_socket", return_value=path):
            assert app.attach_daemon() == ["/j1", "/j2"]
        attached = app.attached
        assert attached is not None
        assert attached.getpeername() == str(path)
        app.on_unmount()
        assert attached.fileno() == -1
    assert received == [b'{"command":"attach"}\n', b"closed"]


def test_detached_attach_reports_missing_or_rejected_daemon(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with mock.patch("labnotes.tui.run_app.daemon_socket", return_value=None):
        with pytest.raises(ValueError, match="No daemon"):
            app.attach_daemon()
    for path, received in daemon_sending(reply=b'{"ok":false,"error":"busy"}\n'):
        with mock.patch("labnotes.tui.run_app.daemon_socket", return_value=path):
            with pytest.raises(ValueError, match="busy"):
                app.attach_daemon()
    assert app.attached is None
    assert received == [b'{"command":"attach"}\n', b"closed"]
