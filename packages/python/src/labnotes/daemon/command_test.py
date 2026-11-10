from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.command import command


def test_command_reports_no_daemon() -> None:
    with mock.patch("labnotes.daemon.command.daemon_socket", return_value=None):
        with pytest.raises(ValueError, match="No daemon is running"):
            command(mock.Mock(), "exp", {"command": "stop_all"})


def test_failed_connect_cleans_stale_record(tmp_path: Path) -> None:
    path = tmp_path / "stale.sock"
    record = tmp_path / "socket.record"
    path.touch()
    record.touch()
    client = mock.MagicMock()
    client.connect.side_effect = OSError("refused")
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
        mock.patch("labnotes.daemon.command.socket_record", return_value=record),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        with pytest.raises(ValueError, match="No daemon is running"):
            command(mock.Mock(), "exp", {"command": "ping"})
    assert not path.exists()
    assert not record.exists()


def test_command_sends_one_request_and_reads_one_reply(tmp_path: Path) -> None:
    path = tmp_path / "daemon.sock"
    client = mock.MagicMock()
    replies = client.makefile.return_value.__enter__.return_value
    replies.readline.return_value = '{"ok":true}\n'
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        assert command(mock.Mock(), "exp", {"command": "ping"}) == {"ok": True}
    client.settimeout.assert_called_once_with(10)
    client.connect.assert_called_once_with(str(path))
    client.sendall.assert_called_once_with(b'{"command": "ping"}\n')
    replies.readline.assert_called_once_with()


@pytest.mark.parametrize("action", ["start", "restart"])
def test_start_commands_allow_daemon_preparation_time(
    tmp_path: Path, action: str
) -> None:
    client = mock.MagicMock()
    client.makefile.return_value.__enter__.return_value.readline.return_value = (
        '{"ok":true}\n'
    )
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=tmp_path),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        assert command(mock.Mock(), "exp", {"command": action}) == {"ok": True}
    assert client.settimeout.call_args_list == [mock.call(10), mock.call(40)]


def test_command_reports_connection_closed_without_reply(tmp_path: Path) -> None:
    client = mock.MagicMock()
    client.makefile.return_value.__enter__.return_value.readline.return_value = ""
    with (
        mock.patch(
            "labnotes.daemon.command.daemon_socket", return_value=tmp_path / "s.sock"
        ),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        with pytest.raises(ValueError, match="closed without a reply"):
            command(mock.Mock(), "exp", {"command": "ping"})


def test_failed_connect_to_a_vanished_socket_still_reports_no_daemon(
    tmp_path: Path,
) -> None:
    record = tmp_path / "socket.record"
    record.touch()
    with (
        mock.patch(
            "labnotes.daemon.command.daemon_socket", return_value=tmp_path / "gone"
        ),
        mock.patch("labnotes.daemon.command.socket_record", return_value=record),
    ):
        with pytest.raises(ValueError, match="No daemon is running"):
            command(mock.Mock(), "exp", {"command": "ping"})
    assert not record.exists()


def test_reply_timeout_keeps_live_daemon_discoverable(tmp_path: Path) -> None:
    path = tmp_path / "live.sock"
    record = tmp_path / "socket.record"
    path.touch()
    record.touch()
    client = mock.MagicMock()
    client.makefile.return_value.__enter__.return_value.readline.side_effect = (
        TimeoutError("timed out")
    )
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
        mock.patch("labnotes.daemon.command.socket_record", return_value=record),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        with pytest.raises(ValueError, match="timed out waiting for a reply"):
            command(mock.Mock(), "exp", {"command": "start"})
    assert path.exists()
    assert record.exists()


def test_connect_timeout_keeps_live_daemon_discoverable(tmp_path: Path) -> None:
    path = tmp_path / "live.sock"
    record = tmp_path / "socket.record"
    path.touch()
    record.touch()
    client = mock.MagicMock()
    client.connect.side_effect = TimeoutError("timed out")
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
        mock.patch("labnotes.daemon.command.socket_record", return_value=record),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        with pytest.raises(ValueError, match="Timed out connecting"):
            command(mock.Mock(), "exp", {"command": "start"})
    assert path.exists()
    assert record.exists()


def test_reply_io_error_keeps_live_daemon_discoverable(tmp_path: Path) -> None:
    path = tmp_path / "live.sock"
    record = tmp_path / "socket.record"
    path.touch()
    record.touch()
    client = mock.MagicMock()
    client.makefile.return_value.__enter__.return_value.readline.side_effect = OSError(
        "connection reset"
    )
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
        mock.patch("labnotes.daemon.command.socket_record", return_value=record),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        with pytest.raises(ValueError, match="command may still be running"):
            command(mock.Mock(), "exp", {"command": "start"})
    assert path.exists()
    assert record.exists()
