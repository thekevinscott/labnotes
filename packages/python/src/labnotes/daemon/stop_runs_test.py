import asyncio
from pathlib import Path
from unittest import mock

from labnotes.daemon.stop_runs import stop_runs


def test_asks_a_running_daemon_to_stop() -> None:
    client = mock.AsyncMock()
    client.post.return_value = mock.Mock()
    with (
        mock.patch(
            "labnotes.daemon.stop_runs.daemon_running",
            new=mock.AsyncMock(return_value=True),
        ) as daemon_running,
        mock.patch("labnotes.daemon.stop_runs.daemon_client") as daemon_client,
    ):
        daemon_client.return_value.__aenter__.return_value = client
        assert asyncio.run(stop_runs(Path("/p")))

    daemon_running.assert_awaited_once_with(Path("/p"))
    daemon_client.assert_called_once_with(Path("/p"))
    client.post.assert_awaited_once_with("/stop")
    client.post.return_value.raise_for_status.assert_called_once_with()


def test_says_when_nothing_runs() -> None:
    with (
        mock.patch(
            "labnotes.daemon.stop_runs.daemon_running",
            new=mock.AsyncMock(return_value=False),
        ),
        mock.patch("labnotes.daemon.stop_runs.daemon_client") as daemon_client,
    ):
        assert not asyncio.run(stop_runs(Path("/p")))

    daemon_client.assert_not_called()
