import asyncio
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.daemon_running import daemon_running


def check(connect: mock.AsyncMock) -> bool:
    with (
        mock.patch(
            "labnotes.daemon.daemon_running.asyncio.open_unix_connection", new=connect
        ),
        mock.patch(
            "labnotes.daemon.daemon_running.socket_path", return_value=Path("/p/s")
        ),
    ):
        return asyncio.run(daemon_running(Path("/p")))


def test_answers_when_something_listens() -> None:
    writer = mock.Mock(wait_closed=mock.AsyncMock())
    connect = mock.AsyncMock(return_value=(mock.Mock(), writer))

    assert check(connect)

    connect.assert_awaited_once_with(Path("/p/s"))
    writer.close.assert_called_once_with()
    writer.wait_closed.assert_awaited_once_with()


@pytest.mark.parametrize("error", [FileNotFoundError, ConnectionRefusedError])
def test_is_down_when_nothing_listens(error: type[Exception]) -> None:
    assert not check(mock.AsyncMock(side_effect=error()))
