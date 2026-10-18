import asyncio
import os


async def wait_for_group(group: int) -> None:
    while True:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.1)
