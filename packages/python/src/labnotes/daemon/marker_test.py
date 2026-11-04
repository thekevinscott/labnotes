import asyncio
from pathlib import Path
from unittest import mock

from labnotes.daemon.marker import daemon_marker


def test_dead_daemon_has_no_running_cells() -> None:
    tables = mock.Mock()
    config = mock.Mock()
    with mock.patch("labnotes.daemon.marker.daemon_socket", return_value=None):
        assert asyncio.run(daemon_marker(tables, config, "exp")) == {
            "daemon": False,
            "running_cells": 0,
        }
    tables.query.assert_not_called()


def test_live_daemon_counts_only_locked_unfinished_runs(tmp_path: Path) -> None:
    (tmp_path / "one").mkdir()
    (tmp_path / "one/run.lock").touch()
    (tmp_path / "two").mkdir()
    (tmp_path / "two/run.lock").touch()
    (tmp_path / "stale").mkdir()
    tables = mock.Mock(
        query=mock.AsyncMock(
            return_value=[
                {"folder": "one"},
                {"folder": "two"},
                {"folder": "stale"},
            ]
        )
    )
    with (
        mock.patch(
            "labnotes.daemon.marker.daemon_socket", return_value=Path("/tmp/x.sock")
        ),
        mock.patch(
            "labnotes.daemon.marker.run_locked", side_effect=[True, False]
        ) as locked,
    ):
        assert asyncio.run(daemon_marker(tables, mock.Mock(root=tmp_path), "a'b")) == {
            "daemon": True,
            "running_cells": 1,
        }
    assert [call.args[0] for call in locked.call_args_list] == [
        tmp_path / "one",
        tmp_path / "two",
    ]
    tables.query.assert_awaited_once_with(
        "SELECT folder FROM runs" " WHERE experiment = 'a''b' AND ended IS NULL"
    )
