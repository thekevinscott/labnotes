import asyncio
from collections.abc import Callable
from pathlib import Path

import httpx2

from labnotes.daemon.daemon_client import daemon_client
from labnotes.daemon.last_stderr import last_stderr
from labnotes.daemon.run_logs import RunLogs
from labnotes.utils.run_usage import run_usage

Event = dict[str, object]
TAIL_SECONDS = 1.0
USAGE_SECONDS = 30.0


async def watch_daemon(root: Path, follow: bool, emit: Callable[[Event], None]) -> None:
    logs = RunLogs()

    def tail() -> None:
        for line in logs.latest():
            emit(line)

    async def keep_tailing() -> None:
        while True:
            await asyncio.sleep(TAIL_SECONDS)
            tail()

    async def sample() -> None:
        for (experiment, run), folder in list(logs.folders.items()):
            if (experiment, run) not in logs.folders:
                continue
            usage = await run_usage(folder, True)
            if (experiment, run) in logs.folders:
                emit({"event": "usage", "experiment": experiment, "run": run, **usage})

    async def keep_sampling() -> None:
        while True:
            await asyncio.sleep(USAGE_SECONDS)
            await sample()

    tailing = asyncio.create_task(keep_tailing()) if follow else None
    sampling = None
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
                        await sample()
                        if not follow:
                            return
                        sampling = asyncio.create_task(keep_sampling())
                        continue
                    case {"event": "started", "experiment": str(name), "run": str(run)}:
                        logs.add(name, run, Path(str(event["folder"])))
                    case {"event": "ended", "experiment": str(name), "run": str(run)}:
                        tail()
                        folder = logs.folders.get((name, run))
                        if event.get("exit_code") != 0 and folder is not None:
                            line = await last_stderr(folder)
                            if line is not None:
                                event = {**event, "last_stderr": line}
                        logs.drop(name, run)
                emit(event)
    except httpx2.TransportError:
        pass
    finally:
        for task in (tailing, sampling):
            if task is not None:
                task.cancel()
