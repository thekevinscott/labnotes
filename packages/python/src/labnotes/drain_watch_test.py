import asyncio
from collections.abc import AsyncIterator
from unittest import mock

from labnotes.drain_watch import drain_watch


def test_consumes_every_watch_event() -> None:
    seen: list[int] = []

    async def events() -> AsyncIterator[int]:
        for event in range(3):
            seen.append(event)
            yield event

    db = mock.Mock()
    db.watch.return_value = events()

    asyncio.run(drain_watch(db))

    assert seen == [0, 1, 2]
