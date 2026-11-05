import asyncio
from collections.abc import Collection

DRAIN_SECONDS = 2


async def drain_output(copying: Collection[asyncio.Task[None]]) -> None:
    # A helper the command left running can hold the pipe open past the exit.
    # Stop reading then, so the run ends; the helper's next write gets EPIPE.
    _, lingering = await asyncio.wait(copying, timeout=DRAIN_SECONDS)
    for task in lingering:
        task.cancel()
    await asyncio.gather(*copying, return_exceptions=True)
