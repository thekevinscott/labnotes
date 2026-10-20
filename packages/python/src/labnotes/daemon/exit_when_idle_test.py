import asyncio
from unittest import mock

from labnotes.daemon.exit_when_idle import IDLE_EXIT_SECONDS, exit_when_idle


def watch(idle: list[bool]) -> tuple[mock.Mock, mock.AsyncMock]:
    server = mock.Mock(should_exit=False)
    with mock.patch(
        "labnotes.daemon.exit_when_idle.asyncio.sleep", new=mock.AsyncMock()
    ) as sleep:
        asyncio.run(exit_when_idle(server, mock.Mock(side_effect=idle)))
    return server, sleep


def test_grace_is_between_ten_and_thirty_seconds() -> None:
    assert IDLE_EXIT_SECONDS == 15


def test_exits_after_a_quiet_spell() -> None:
    server, sleep = watch([True] * IDLE_EXIT_SECONDS)

    assert server.should_exit
    assert sleep.await_count == IDLE_EXIT_SECONDS
    sleep.assert_awaited_with(1)


def test_starts_the_count_again_when_busy() -> None:
    server, sleep = watch([True] * 3 + [False] + [True] * IDLE_EXIT_SECONDS)

    assert server.should_exit
    assert sleep.await_count == IDLE_EXIT_SECONDS + 4
