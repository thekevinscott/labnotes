import fcntl
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.client import command, daemon_socket
from labnotes.daemon.socket_path import lock_path, socket_record


def config(root: Path) -> mock.Mock:
    return mock.Mock(
        root=root,
        experiments="{experiment}",
        runs="{experiment}/runs/{run}",
    )


def test_missing_and_stale_socket_are_not_running(tmp_path: Path) -> None:
    project = config(tmp_path)
    assert daemon_socket(project, "exp") is None
    record = socket_record(project, "exp")
    record.parent.mkdir(parents=True)
    stale = tmp_path / "stale.sock"
    stale.touch()
    record.write_text(str(stale))
    lock_path(project, "exp").touch()
    assert daemon_socket(project, "exp") is None
    assert not stale.exists()
    assert not record.exists()


def test_record_without_lock_is_cleaned_as_stale(tmp_path: Path) -> None:
    project = config(tmp_path)
    record = socket_record(project, "exp")
    record.parent.mkdir(parents=True)
    stale = tmp_path / "orphan.sock"
    stale.touch()
    record.write_text(str(stale))
    assert daemon_socket(project, "exp") is None
    assert not stale.exists()
    assert not record.exists()


def test_held_lock_exposes_recorded_socket(tmp_path: Path) -> None:
    project = config(tmp_path)
    record = socket_record(project, "exp")
    record.parent.mkdir(parents=True)
    record.write_text("/tmp/held.sock")
    with lock_path(project, "exp").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert daemon_socket(project, "exp") == Path("/tmp/held.sock")


def test_command_reports_no_daemon(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No daemon is running"):
        command(config(tmp_path), "exp", {"command": "stop_all"})


def test_failed_connect_cleans_stale_record(tmp_path: Path) -> None:
    project = config(tmp_path)
    record = socket_record(project, "exp")
    record.parent.mkdir(parents=True)
    record.write_text(str(tmp_path / "stale.sock"))
    with mock.patch(
        "labnotes.daemon.client.daemon_socket", return_value=tmp_path / "stale.sock"
    ):
        with pytest.raises(ValueError, match="No daemon is running"):
            command(project, "exp", {"command": "ping"})
    assert not record.exists()


def test_command_reads_one_reply_from_unix_socket(tmp_path: Path) -> None:
    import socket
    import threading

    path = tmp_path / "daemon.sock"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(path))
    server.listen()
    received: list[bytes] = []

    def serve() -> None:
        client, _ = server.accept()
        with client:
            received.append(client.recv(1024))
            client.sendall(b'{"ok":true}\n')

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        with mock.patch("labnotes.daemon.client.daemon_socket", return_value=path):
            assert command(config(tmp_path), "exp", {"command": "ping"}) == {"ok": True}
        assert received == [b'{"command": "ping"}\n']
    finally:
        thread.join(timeout=5)
        server.close()


def test_command_reports_connection_closed_without_reply(tmp_path: Path) -> None:
    import socket
    import threading

    path = tmp_path / "daemon.sock"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(path))
    server.listen()

    def serve() -> None:
        client, _ = server.accept()
        client.recv(1024)
        client.close()

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        with mock.patch("labnotes.daemon.client.daemon_socket", return_value=path):
            with pytest.raises(ValueError, match="closed without a reply"):
                command(config(tmp_path), "exp", {"command": "ping"})
    finally:
        thread.join(timeout=5)
        server.close()
