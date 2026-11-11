from collections.abc import Callable
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


def connected(tmp_path: Path, lines: list[str]) -> tuple[mock.MagicMock, Path]:
    client = mock.MagicMock()
    client.makefile.return_value.__enter__.return_value = iter(lines)
    return client, tmp_path / "daemon.sock"


def run_command(
    client: mock.MagicMock,
    path: Path,
    progress: Callable[[str], None] | None = None,
    action: str = "ping",
) -> dict[str, object]:
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        return command(mock.Mock(), "exp", {"command": action}, progress)


def test_command_sends_one_request_and_reads_one_reply(tmp_path: Path) -> None:
    client, path = connected(tmp_path, ['{"ok":true}\n', '{"ignored":true}\n'])
    assert run_command(client, path) == {"ok": True}
    client.settimeout.assert_called_once_with(10)
    client.connect.assert_called_once_with(str(path))
    client.sendall.assert_called_once_with(b'{"command": "ping"}\n')


@pytest.mark.parametrize("action", ["start", "restart"])
def test_command_passes_steps_to_progress_and_waits_without_deadline(
    tmp_path: Path, action: str
) -> None:
    client, path = connected(
        tmp_path, ['{"step":"Snapshotting repo"}\n', '{"ok":true}\n']
    )
    steps: list[str] = []
    assert run_command(client, path, steps.append, action) == {"ok": True}
    assert steps == ["Snapshotting repo"]
    assert client.settimeout.call_args_list == [mock.call(10), mock.call(None)]


def test_a_start_without_progress_still_waits_without_deadline(
    tmp_path: Path,
) -> None:
    client, path = connected(tmp_path, ['{"ok":true}\n'])
    assert run_command(client, path, None, "start") == {"ok": True}
    assert client.settimeout.call_args_list == [mock.call(10), mock.call(None)]


def test_other_commands_keep_the_reply_deadline_with_progress(
    tmp_path: Path,
) -> None:
    client, path = connected(tmp_path, ['{"ok":true}\n'])
    assert run_command(client, path, lambda step: None) == {"ok": True}
    client.settimeout.assert_called_once_with(10)


def test_command_without_progress_skips_steps(tmp_path: Path) -> None:
    client, path = connected(tmp_path, ['{"step":"Starting run"}\n', '{"ok":1}\n'])
    assert run_command(client, path) == {"ok": 1}
    client.settimeout.assert_called_once_with(10)


def test_command_reports_connection_closed_without_reply(tmp_path: Path) -> None:
    client, path = connected(tmp_path, ['{"step":"Starting run"}\n'])
    with pytest.raises(ValueError, match="closed without a reply"):
        run_command(client, path)


def test_command_reports_a_reset_connection_as_closed(tmp_path: Path) -> None:
    client, path = connected(tmp_path, [])
    client.sendall.side_effect = ConnectionResetError("reset")
    with pytest.raises(ValueError, match="closed without a reply"):
        run_command(client, path)


def test_a_reply_timeout_keeps_the_daemon_findable(tmp_path: Path) -> None:
    record = tmp_path / "socket.record"
    record.touch()
    client, path = connected(tmp_path, [])
    path.touch()
    client.makefile.return_value.__enter__.side_effect = TimeoutError
    with mock.patch("labnotes.daemon.command.socket_record", return_value=record):
        with pytest.raises(ValueError, match="did not reply in 10s"):
            run_command(client, path)
    assert path.exists()
    assert record.exists()


def test_a_connect_timeout_keeps_the_daemon_findable(tmp_path: Path) -> None:
    record = tmp_path / "socket.record"
    record.touch()
    client, path = connected(tmp_path, [])
    path.touch()
    client.connect.side_effect = TimeoutError
    with mock.patch("labnotes.daemon.command.socket_record", return_value=record):
        with pytest.raises(ValueError, match="did not answer in 10s"):
            run_command(client, path)
    assert path.exists()
    assert record.exists()


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


def test_failed_connect_without_a_record_still_reports_no_daemon(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stale.sock"
    path.touch()
    client = mock.MagicMock()
    client.connect.side_effect = ConnectionRefusedError("refused")
    with (
        mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
        mock.patch(
            "labnotes.daemon.command.socket_record",
            return_value=tmp_path / "missing.record",
        ),
        mock.patch("labnotes.daemon.command.socket.socket") as sockets,
    ):
        sockets.return_value.__enter__.return_value = client
        with pytest.raises(ValueError, match="No daemon is running"):
            command(mock.Mock(), "exp", {"command": "ping"})
    assert not path.exists()
