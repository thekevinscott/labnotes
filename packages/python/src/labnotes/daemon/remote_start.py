import asyncio
import dataclasses
from collections.abc import Callable
from pathlib import Path

import httpx2

from labnotes.daemon.daemon_client import daemon_client
from labnotes.daemon.ensure_daemon import ensure_daemon
from labnotes.models import Controls, LabnotesConfig, Listen, Report, Start


def remote_start(
    config: LabnotesConfig,
    name: str,
    experiment_config: Path | None,
    concurrency: int | None,
    timeout: float | None = None,
    only: dict[str, str] | None = None,
    args: list[str] | None = None,
    setup: str | None = None,
    teardown: str | None = None,
) -> Start:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        try:
            return await follow(report, listen)
        except (OSError, httpx2.TransportError) as error:
            cause = str(error) or type(error).__name__
            raise ValueError(f"Can't reach the labnotes daemon: {cause}") from error

    async def follow(report: Report, listen: Listen) -> list[dict[str, object]]:
        await ensure_daemon(config)
        sending: set[asyncio.Task[httpx2.Response]] = set()
        results: list[dict[str, object]] = []
        async with (
            daemon_client(config.root) as client,
            client.stream("GET", "/events") as response,
        ):
            events = aiter(httpx2.EventSource(response))
            first = await anext(events, None)
            if first is None:
                raise ValueError("Lost the labnotes daemon.")
            connected: dict[str, object] = first.json()  # type: ignore[assignment]
            reply = await client.post(
                f"/experiments/{name}/run",
                json={
                    "client": connected["client"],
                    "experiment_config": None
                    if experiment_config is None
                    else str(experiment_config.resolve()),
                    "concurrency": concurrency,
                    "timeout": timeout,
                    "only": only,
                    "args": args,
                    "setup": setup,
                    "teardown": teardown,
                },
            )
            if reply.status_code != 202:
                raise ValueError(reply.json()["error"])

            def send(action: str) -> Callable[..., None]:
                def post(*args: object) -> None:
                    task = asyncio.create_task(
                        client.post(
                            f"/experiments/{name}/{action}", json={"args": list(args)}
                        )
                    )
                    sending.add(task)
                    task.add_done_callback(sending.discard)

                return post

            listen(Controls(*(send(f.name) for f in dataclasses.fields(Controls))))
            async for message in events:
                event: dict[str, object] = message.json()  # type: ignore[assignment]
                if event.pop("experiment", None) != name:
                    continue
                match event:
                    case {"event": "done", "error": None}:
                        await asyncio.gather(*sending)
                        return results
                    case {"event": "done", "error": error}:
                        raise ValueError(f"{name} stopped: {error}")
                    case {"event": "ended"}:
                        results.append(event)
                report(event)
        raise ValueError("Lost the labnotes daemon.")

    return start
