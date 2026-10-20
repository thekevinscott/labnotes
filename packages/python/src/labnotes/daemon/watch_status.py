import asyncio
from collections.abc import Callable
from pathlib import Path

from labnotes.daemon.daemon_running import daemon_running
from labnotes.daemon.watch_daemon import watch_daemon

POLL_SECONDS = 1.0


async def watch_status(
    root: Path, follow: bool, emit: Callable[[dict[str, object]], None]
) -> None:
    while True:
        if await daemon_running(root):
            await watch_daemon(root, follow, emit)
        if not follow:
            return
        await asyncio.sleep(POLL_SECONDS)
