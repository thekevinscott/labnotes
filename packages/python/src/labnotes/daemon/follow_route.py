"""Follow one of the daemon's read routes, starting a daemon when none is found."""

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import httpx2

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.ensure import ensure_daemon
from labnotes.daemon.quiet_late_wakeup import quiet_late_wakeup
from labnotes.models import LabnotesConfig

MAX_EVENT_BYTES = 16 * 1024 * 1024
RETRY_SECONDS = 0.5


async def follow_route(
    config: LabnotesConfig,
    name: str,
    route: str,
    ensure: Callable[[LabnotesConfig, str], Awaitable[None]] = ensure_daemon,
) -> AsyncGenerator[tuple[str, Any], None]:
    """Yield each event as it arrives; on a dropped stream, reconnect and resume.

    Holds no events: the caller handles each one before the next is read.
    """
    asyncio.get_running_loop().set_exception_handler(quiet_late_wakeup)
    last: str | None = None
    while True:
        await ensure(config, name)
        path = daemon_socket(config, name)
        if path is not None:
            async with httpx2.AsyncClient(
                transport=httpx2.AsyncHTTPTransport(uds=str(path)),
                base_url="http://labnotes",
                timeout=httpx2.Timeout(10, read=None),
            ) as client:
                headers = {} if last is None else {"Last-Event-ID": last}
                try:
                    async with client.stream("GET", route, headers=headers) as response:
                        if response.is_error:
                            rejected = json.loads(await response.aread())
                            raise ValueError(str(rejected.get("error", route)))
                        source = httpx2.EventSource(
                            response, max_event_size=MAX_EVENT_BYTES
                        )
                        async for event in source:
                            if event.id:
                                last = event.id
                            yield event.event, event.json()
                except (httpx2.HTTPError, httpx2.StreamError):
                    pass
        await asyncio.sleep(RETRY_SECONDS)
