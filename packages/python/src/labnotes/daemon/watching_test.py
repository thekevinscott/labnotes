import asyncio
from unittest import mock

import anyio
import pytest

from labnotes.daemon.watching import watching


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


def test_a_close_that_waits_finishes_inside_a_cancelled_scope() -> None:
    finished: list[bool] = []

    class Changes:
        async def aclose(self) -> None:
            await asyncio.sleep(0.01)
            finished.append(True)

    async def scenario() -> None:
        with anyio.CancelScope() as scope:
            async with watching(tables(Changes())):
                scope.cancel()
                await anyio.sleep(1)
        assert finished == [True]

    asyncio.run(scenario())
