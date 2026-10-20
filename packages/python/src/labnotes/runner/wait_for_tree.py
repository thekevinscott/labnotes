import asyncio

import psutil


async def wait_for_tree(processes: set[psutil.Process]) -> None:
    while any(process.is_running() for process in processes):
        await asyncio.sleep(0.1)
