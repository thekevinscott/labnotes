import asyncio
import dataclasses
import itertools
import json
from collections.abc import AsyncIterator
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from labnotes.models import Controls, LabnotesConfig
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.run_experiment import run_experiment
from labnotes.runner.stop_then_kill import GRACE_SECONDS

Event = dict[str, object]
ACTIONS = frozenset(field.name for field in dataclasses.fields(Controls))


def daemon_app(config: LabnotesConfig) -> Starlette:
    sessions: dict[str, Controls | None] = {}
    owners: dict[str, int] = {}
    clients: dict[int, asyncio.Queue[Event]] = {}
    watchers: set[int] = set()
    history: dict[str, list[Event]] = {}
    ids = itertools.count(1)
    tasks: set[asyncio.Task[str | None]] = set()

    def broadcast(event: Event) -> None:
        for queue in clients.values():
            queue.put_nowait(event)

    def refuse(status: int, error: str) -> Response:
        return JSONResponse({"error": error}, status_code=status)

    def release(client: int) -> None:
        for name, owner in list(owners.items()):
            controls = sessions.get(name)
            if owner == client and controls is not None:
                del owners[name]
                controls.finish()

    def record(event: Event) -> None:
        history.setdefault(str(event["experiment"]), []).append(event)
        broadcast(event)

    async def events(request: Request) -> Response:
        client = next(ids)
        watching = request.query_params.get("watch") == "1"

        async def stream() -> AsyncIterator[str]:
            clients[client] = asyncio.Queue()
            if watching:
                watchers.add(client)
                for past in history.values():
                    for old in past:
                        clients[client].put_nowait(old)
                clients[client].put_nowait({"event": "replayed"})
            try:
                event: Event = {"event": "connected", "client": client}
                while True:
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                    event = await clients[client].get()
            finally:
                del clients[client]
                watchers.discard(client)
                release(client)

        return StreamingResponse(stream(), media_type="text/event-stream")

    async def start(name: str, body: dict[str, object]) -> Response:
        path = body.get("experiment_config")
        try:
            experiment, concurrency = await prepare_experiment(
                config,
                name,
                None if path is None else Path(str(path)),
                body.get("concurrency"),  # type: ignore[arg-type]
            )
        except ValueError as error:
            return refuse(400, str(error))
        ready = asyncio.Event()
        owner = body.get("client")
        if isinstance(owner, int):
            owners[name] = owner

        def listen(controls: Controls) -> None:
            sessions[name] = controls
            ready.set()
            if name in owners and owners[name] not in clients:
                release(owners[name])

        async def session() -> str | None:
            error = None
            try:
                await run_experiment(
                    config,
                    name,
                    experiment,
                    concurrency,
                    lambda event: record({**event, "experiment": name}),
                    listen,
                )
            # Clients hear why the session ended; the daemon keeps serving.
            except Exception as failure:  # noqa: BLE001
                error = str(failure)
            del sessions[name]
            owners.pop(name, None)
            history.pop(name, None)
            broadcast({"event": "done", "experiment": name, "error": error})
            return error

        task = asyncio.create_task(session())
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        waiting = asyncio.create_task(ready.wait())
        await asyncio.wait({task, waiting}, return_when=asyncio.FIRST_COMPLETED)
        waiting.cancel()
        if not ready.is_set():
            return refuse(500, str(task.result()))
        return JSONResponse({}, status_code=202)

    async def run(request: Request) -> Response:
        name = request.path_params["name"]
        body = await request.json()
        if name in sessions:
            return refuse(409, f"{name} is already running.")
        sessions[name] = None
        response = await start(name, body)
        if response.status_code != 202:
            sessions.pop(name, None)
        return response

    async def control(request: Request) -> Response:
        name, action = request.path_params["name"], request.path_params["action"]
        body = await request.json()
        controls = sessions.get(name)
        if action not in ACTIONS or controls is None:
            return refuse(404, f"No {action} for {name}.")
        getattr(controls, action)(*body["args"])
        return JSONResponse({})

    def stop_all() -> None:
        stopping = [controls for controls in sessions.values() if controls]

        def interrupt() -> None:
            for controls in stopping:
                controls.interrupt()

        interrupt()
        asyncio.get_running_loop().call_later(GRACE_SECONDS, interrupt)

    async def stop(request: Request) -> Response:
        stop_all()
        return JSONResponse({})

    app = Starlette(
        routes=[
            Route("/events", events),
            Route("/stop", stop, methods=["POST"]),
            Route("/experiments/{name}/run", run, methods=["POST"]),
            Route("/experiments/{name}/{action}", control, methods=["POST"]),
        ]
    )
    app.state.idle = (
        lambda: all(client in watchers for client in clients) and not sessions
    )
    app.state.stop = stop_all
    return app
