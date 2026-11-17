import asyncio
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.daemon.watching import watching


@pytest.fixture(autouse=True)
def anyio() -> Iterator[mock.Mock]:
    with mock.patch("labnotes.daemon.watching.anyio") as found:
        yield found


def tables(changes: object) -> mock.Mock:
    return mock.Mock(watch=mock.Mock(return_value=changes))


def test_yields_the_stream_and_closes_it_on_exit() -> None:
    changes = mock.Mock(aclose=mock.AsyncMock())

    async def scenario() -> None:
        async with watching(tables(changes)) as found:
            assert found is changes
            changes.aclose.assert_not_awaited()

    asyncio.run(scenario())

    changes.aclose.assert_awaited_once_with()


def test_closes_the_stream_when_the_body_raises() -> None:
    changes = mock.Mock(aclose=mock.AsyncMock())

    async def scenario() -> None:
        async with watching(tables(changes)):
            raise LookupError

    with pytest.raises(LookupError):
        asyncio.run(scenario())

    changes.aclose.assert_awaited_once_with()


def test_a_stream_without_aclose_is_yielded_and_left_alone() -> None:
    changes = object()

    async def scenario() -> object:
        async with watching(tables(changes)) as found:
            return found

    assert asyncio.run(scenario()) is changes


def test_the_close_runs_in_a_shielded_cancel_scope(anyio: mock.Mock) -> None:
    order: list[str] = []
    scope = anyio.CancelScope.return_value
    scope.__enter__.side_effect = lambda: order.append("enter")
    scope.__exit__.side_effect = lambda *_: order.append("exit")
    changes = mock.Mock(
        aclose=mock.AsyncMock(side_effect=lambda: order.append("close"))
    )

    async def scenario() -> None:
        async with watching(tables(changes)):
            pass

    asyncio.run(scenario())

    anyio.CancelScope.assert_called_once_with(shield=True)
    assert order == ["enter", "close", "exit"]
