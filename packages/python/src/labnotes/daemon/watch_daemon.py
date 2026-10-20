import asyncio
from collections.abc import Callable
from pathlib import Path

import httpx2

from labnotes.daemon.daemon_client import daemon_client
from labnotes.daemon.run_logs import RunLogs

Event = dict[str, object]
TAIL_SECONDS = 1.0


async def watch_daemon(root: Path, follow: bool, emit: Callable[[Event], None]) -> None:
    logs = RunLogs()

    def tail() -> None:
        for line in logs.latest():
            emit(line)

    async def keep_tailing() -> None:
        while True:
            await asyncio.sleep(TAIL_SECONDS)
            tail()

    tailing = asyncio.create_task(keep_tailing()) if follow else None
    try:
        async with (
            daemon_client(root) as client,
            client.stream("GET", "/events", params={"watch": "1"}) as response,
        ):
            events = aiter(httpx2.EventSource(response))
            await anext(events)
            async for message in events:
                event: Event = message.json()  # type: ignore[assignment]
                match event:
                    case {"event": "replayed"}:
                        tail()
                        if not follow:
                            return
                        continue
                    case {"event": "started", "experiment": str(name), "run": str(run)}:
                        logs.add(name, run, Path(str(event["folder"])))
                    case {"event": "ended", "experiment": str(name), "run": str(run)}:
                        tail()
                        logs.drop(name, run)
                emit(event)
    except httpx2.TransportError:
        pass
    finally:
        if tailing is not None:
            tailing.cancel()
