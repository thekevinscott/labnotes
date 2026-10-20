import asyncio
from unittest import mock

from labnotes.runner.wait_for_tree import wait_for_tree


def test_polls_until_every_process_is_gone() -> None:
    first = mock.Mock(is_running=mock.Mock(side_effect=[True, False, False]))
    second = mock.Mock(is_running=mock.Mock(side_effect=[True, False]))
    with mock.patch(
        "labnotes.runner.wait_for_tree.asyncio.sleep", new=mock.AsyncMock()
    ) as sleep:
        asyncio.run(wait_for_tree([first, second]))  # type: ignore[arg-type]

    assert sleep.await_args_list == [mock.call(0.1)] * 2


def test_returns_at_once_when_nothing_lingers() -> None:
    with mock.patch(
        "labnotes.runner.wait_for_tree.asyncio.sleep", new=mock.AsyncMock()
    ) as sleep:
        asyncio.run(wait_for_tree(set()))

    sleep.assert_not_awaited()
