import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.watch_status import watch_status


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.AsyncMock]]:
    with (
        mock.patch(
            "labnotes.daemon.watch_status.daemon_running", new=mock.AsyncMock()
        ) as daemon_running,
        mock.patch(
            "labnotes.daemon.watch_status.watch_daemon", new=mock.AsyncMock()
        ) as watch_daemon,
        mock.patch(
            "labnotes.daemon.watch_status.asyncio.sleep", new=mock.AsyncMock()
        ) as sleep,
    ):
        yield {
            "daemon_running": daemon_running,
            "watch_daemon": watch_daemon,
            "sleep": sleep,
        }


@pytest.mark.parametrize("running", [True, False])
def test_reports_once_without_follow(
    collaborators: dict[str, mock.AsyncMock], running: bool
) -> None:
    collaborators["daemon_running"].return_value = running
    emit = mock.Mock()

    asyncio.run(watch_status(Path("/p"), False, emit))

    collaborators["daemon_running"].assert_awaited_once_with(Path("/p"))
    assert collaborators["watch_daemon"].await_count == running
    if running:
        collaborators["watch_daemon"].assert_awaited_once_with(Path("/p"), False, emit)
    collaborators["sleep"].assert_not_awaited()


def test_waits_for_each_daemon_when_following(
    collaborators: dict[str, mock.AsyncMock],
) -> None:
    collaborators["daemon_running"].side_effect = [False, True, False]
    collaborators["sleep"].side_effect = [None, None, asyncio.CancelledError()]
    emit = mock.Mock()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(watch_status(Path("/p"), True, emit))

    collaborators["watch_daemon"].assert_awaited_once_with(Path("/p"), True, emit)
    collaborators["sleep"].assert_awaited_with(1.0)
    assert collaborators["sleep"].await_count == 3
