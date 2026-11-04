import asyncio
from pathlib import Path
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


def test_startup_failure_reports_stderr(tmp_path: Path) -> None:
    project = config(tmp_path)
    process = mock.Mock()
    process.poll.return_value = 2
    with (
        mock.patch("labnotes.daemon.ensure.daemon_socket", return_value=None),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", return_value=process),
    ):
        (tmp_path / "daemon.stderr").write_text("bad config")
        with pytest.raises(ValueError, match="bad config"):
            asyncio.run(ensure_daemon(project, "exp"))


def test_startup_timeout_names_limit(tmp_path: Path) -> None:
    project = config(tmp_path)
    process = mock.Mock()
    process.poll.return_value = None
    with (
        mock.patch("labnotes.daemon.ensure.daemon_socket", return_value=None),
        mock.patch("labnotes.daemon.ensure.discovery_folder", return_value=tmp_path),
        mock.patch("labnotes.daemon.ensure.START_SECONDS", 0),
        mock.patch("labnotes.daemon.ensure.subprocess.Popen", return_value=process),
    ):
        with pytest.raises(ValueError, match="did not start in 0s"):
            asyncio.run(ensure_daemon(project, "exp"))
