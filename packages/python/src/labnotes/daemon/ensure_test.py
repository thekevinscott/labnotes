import asyncio
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.daemon.ensure import ensure_daemon


def config(root: Path) -> mock.Mock:
    return mock.Mock(path=root / ".labnotes.toml", root=root)


def test_existing_daemon_needs_no_new_process(tmp_path: Path) -> None:
    with (
        mock.patch(
            "labnotes.daemon.ensure.daemon_socket", return_value=tmp_path / "s.sock"
        ),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen") as popen,
    ):
        asyncio.run(ensure_daemon(config(tmp_path), "exp"))
    popen.assert_not_called()


def test_detached_start_waits_for_socket(tmp_path: Path) -> None:
    project = config(tmp_path)
    process = mock.Mock()
    process.poll.return_value = None
    with (
        mock.patch(
            "labnotes.daemon.ensure.daemon_socket",
            side_effect=[None, None, tmp_path / "s.sock"],
        ),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch(
            "labnotes.daemon.ensure.subprocess.Popen", return_value=process
        ) as popen,
        mock.patch(
            "labnotes.daemon.ensure.asyncio.sleep", new=mock.AsyncMock()
        ) as sleep,
    ):
        asyncio.run(ensure_daemon(project, "exp"))
    args, kwargs = popen.call_args
    assert args[0][-2:] == ["daemon", "exp"]
    assert kwargs["start_new_session"] is True
    assert kwargs["cwd"] == tmp_path
    assert sleep.await_count == 1
    assert (tmp_path / "daemon.stderr").stat().st_mode & 0o777 == 0o600


def failing_popen(output: str) -> mock.Mock:
    def popen(*args: object, **kwargs: Any) -> mock.Mock:
        if output:
            kwargs["stderr"].write(output.encode())
            kwargs["stderr"].flush()
        return mock.Mock(**{"poll.return_value": 2})

    return mock.Mock(side_effect=popen)


def run_failing_start(tmp_path: Path, output: str) -> str:
    with (
        mock.patch("labnotes.daemon.ensure.daemon_socket", return_value=None),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", failing_popen(output)),
        mock.patch("labnotes.daemon.ensure.iso_time", return_value="T"),
        mock.patch("labnotes.daemon.ensure.time.time", return_value=0.0),
    ):
        with pytest.raises(ValueError) as error:
            asyncio.run(ensure_daemon(config(tmp_path), "exp"))
    return str(error.value)


def test_startup_failure_reports_stderr(tmp_path: Path) -> None:
    assert run_failing_start(tmp_path, "bad config") == "bad config"


def test_startup_failure_omits_earlier_launches(tmp_path: Path) -> None:
    (tmp_path / "daemon.stderr").write_text("old failure\n")
    message = run_failing_start(tmp_path, "new failure")
    assert message == "new failure"
    assert "old failure" not in message
    assert (tmp_path / "daemon.stderr").read_text().startswith("old failure\n--- T")


def test_startup_failure_without_new_output_ignores_old_text(tmp_path: Path) -> None:
    (tmp_path / "daemon.stderr").write_text("old failure\n")
    message = run_failing_start(tmp_path, "")
    assert message == "Daemon for exp exited during startup."


def test_launch_header_is_written_before_popen(tmp_path: Path) -> None:
    seen: list[str] = []

    def popen(*args: object, **kwargs: Any) -> mock.Mock:
        seen.append((tmp_path / "daemon.stderr").read_text())
        return mock.Mock(**{"poll.return_value": 2})

    with (
        mock.patch("labnotes.daemon.ensure.daemon_socket", return_value=None),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", side_effect=popen),
        mock.patch("labnotes.daemon.ensure.iso_time", return_value="T") as stamp,
        mock.patch("labnotes.daemon.ensure.time.time", return_value=12.0),
    ):
        with pytest.raises(ValueError):
            asyncio.run(ensure_daemon(config(tmp_path), "exp"))
    stamp.assert_called_once_with(12.0)
    assert seen == ["--- T starting daemon for exp\n"]


def test_zero_exit_waits_for_other_daemon_to_publish_socket(tmp_path: Path) -> None:
    process = mock.Mock()
    process.poll.return_value = 0
    socket = tmp_path / "winner.sock"
    with (
        mock.patch(
            "labnotes.daemon.ensure.daemon_socket", side_effect=[None, None, socket]
        ),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", return_value=process),
        mock.patch(
            "labnotes.daemon.ensure.asyncio.sleep", new=mock.AsyncMock()
        ) as sleep,
    ):
        asyncio.run(ensure_daemon(config(tmp_path), "exp"))
    process.poll.assert_called_once()
    sleep.assert_not_awaited()


def test_zero_exit_without_a_winner_reports_the_exit(tmp_path: Path) -> None:
    process = mock.Mock(**{"poll.return_value": 0})
    with (
        mock.patch("labnotes.daemon.ensure.daemon_socket", return_value=None),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", return_value=process),
    ):
        with pytest.raises(ValueError, match="exited during startup"):
            asyncio.run(ensure_daemon(config(tmp_path), "exp"))


def test_startup_waits_past_any_deadline_and_reports_the_step(
    tmp_path: Path,
) -> None:
    process = mock.Mock(**{"poll.return_value": None})
    steps: list[str] = []
    with (
        mock.patch(
            "labnotes.daemon.ensure.daemon_socket",
            side_effect=[None] * 501 + [tmp_path / "s.sock"],
        ),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", return_value=process),
        mock.patch(
            "labnotes.daemon.ensure.asyncio.sleep", new=mock.AsyncMock()
        ) as sleep,
    ):
        asyncio.run(ensure_daemon(config(tmp_path), "exp", steps.append))
    assert steps == ["Starting daemon"]
    assert sleep.await_args_list == [mock.call(0.1)] * 500


def test_signal_death_reports_stderr_and_folder_is_created(tmp_path: Path) -> None:
    folder = tmp_path / "state" / "labnotes" / "key"
    process = mock.Mock()
    process.poll.return_value = -9
    with (
        mock.patch("labnotes.daemon.ensure.daemon_socket", return_value=None),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=folder),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", return_value=process),
        mock.patch("labnotes.daemon.ensure.asyncio.sleep", new=mock.AsyncMock()),
    ):
        with pytest.raises(ValueError, match="exited during startup"):
            asyncio.run(ensure_daemon(config(tmp_path), "exp"))
    assert (folder / "daemon.stderr").exists()
