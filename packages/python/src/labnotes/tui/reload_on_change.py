import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable


async def reload_on_change(
    changes: AsyncIterable[object], reload: Callable[[], Awaitable[None]]
) -> None:
    # Changes that land during a reload collapse into one more reload.
    stale = asyncio.Event()

    async def mark() -> None:
        async for _ in changes:
            stale.set()

    marker = asyncio.create_task(mark())
    try:
        while True:
            await reload()
            await stale.wait()
            stale.clear()
    finally:
        marker.cancel()
