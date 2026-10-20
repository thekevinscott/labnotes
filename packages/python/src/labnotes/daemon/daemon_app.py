import asyncio
import contextlib
import dataclasses
import json
from collections.abc import AsyncIterator
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from labnotes.models import Controls, LabnotesConfig
from labnotes.runner.hold_folder import hold_folder
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.run_experiment import run_experiment
from labnotes.runner.stop_then_kill import GRACE_SECONDS

Event = dict[str, object]
ACTIONS = frozenset(field.name for field in dataclasses.fields(Controls))


def daemon_app(config: LabnotesConfig) -> Starlette:
    sessions: dict[str, Controls | None] = {}
    clients: set[asyncio.Queue[Event]] = set()
    tasks: set[asyncio.Task[str | None]] = set()

    def broadcast(event: Event) -> None:
        for queue in clients:
            queue.put_nowait(event)

    def refuse(status: int, error: str) -> Response:
        return JSONResponse({"error": error}, status_code=status)

    async def events(request: Request) -> Response:
        queue: asyncio.Queue[Event] = asyncio.Queue()

        async def stream() -> AsyncIterator[str]:
            clients.add(queue)
            try:
                event: Event = {"event": "connected"}
                while True:
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                    event = await queue.get()
            finally:
                clients.discard(queue)

        return StreamingResponse(stream(), media_type="text/event-stream")

    async def start(name: str, body: dict[str, object]) -> Response:
        path = body.get("experiment_config")
        try:
            experiment, concurrency, runs = await prepare_experiment(
                config,
                name,
                None if path is None else Path(str(path)),
                body.get("concurrency"),  # type: ignore[arg-type]
            )
        except ValueError as error:
            return refuse(400, str(error))
        lock = contextlib.ExitStack()
        try:
            lock.enter_context(hold_folder(runs))
        except BlockingIOError:
            return refuse(409, f"{name} is already running ({runs} is held).")
        ready = asyncio.Event()

        def listen(controls: Controls) -> None:
            sessions[name] = controls
            ready.set()

        async def session() -> str | None:
            error = None
            with lock:
                try:
                    await run_experiment(
                        config,
                        name,
                        experiment,
                        concurrency,
                        lambda event: broadcast({**event, "experiment": name}),
                        listen,
                    )
                # Clients hear why the session ended; the daemon keeps serving.
                except Exception as failure:  # noqa: BLE001
                    error = str(failure)
            del sessions[name]
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
    app.state.idle = lambda: not clients and not sessions
    app.state.stop = stop_all
    return app
