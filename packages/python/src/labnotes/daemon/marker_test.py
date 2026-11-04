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


def test_live_daemon_counts_unfinished_run_rows() -> None:
    tables = mock.Mock(query=mock.AsyncMock(return_value=[{"running_cells": 2}]))
    with mock.patch(
        "labnotes.daemon.marker.daemon_socket", return_value=Path("/tmp/x.sock")
    ):
        assert asyncio.run(daemon_marker(tables, mock.Mock(), "a'b")) == {
            "daemon": True,
            "running_cells": 2,
        }
    tables.query.assert_awaited_once_with(
        "SELECT count(*) AS running_cells FROM runs"
        " WHERE experiment = 'a''b' AND ended IS NULL"
    )
