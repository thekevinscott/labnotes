import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any
from urllib.parse import quote

from labnotes.daemon.ensure import ensure_daemon
from labnotes.daemon.follow_route import follow_route
from labnotes.models import LabnotesConfig

RETRY_SECONDS = 0.5


async def follow_run_files(
    config: LabnotesConfig,
    name: str,
    run: str,
    ensure: Callable[[LabnotesConfig, str], Awaitable[None]] = ensure_daemon,
) -> AsyncGenerator[tuple[str, Any], None]:
    """Follow one run's file list from the daemon.

    A run the TUI has just started can reach the daemon's tables a moment
    later, so its route answers not found until then.
    """
    route = f"/runs/{quote(run)}/files"
    while True:
        try:
            async for event in follow_route(config, name, route, ensure):
                yield event
        except ValueError:
            pass
        await asyncio.sleep(RETRY_SECONDS)
