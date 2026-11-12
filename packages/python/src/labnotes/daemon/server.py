"""Own experiment invocations behind a private HTTP socket."""

import asyncio
import fcntl
import json
import operator
import os
import signal
import socket
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from labnotes.daemon.listening import listening
from labnotes.daemon.sse import sse
from labnotes.daemon.socket_path import (
    discovery_folder,
    lock_path,
    socket_path,
    socket_record,
)
from labnotes.models import Controls, LabnotesConfig
from labnotes.runner.stamp_event import stamp_event
from labnotes.runner.start_experiment import start_experiment

IDLE_SECONDS = 5.0
LIVE_STATE_NOTE = (
    "Live state for running labnotes daemons: locks and socket records.\n"
    "Do not delete this folder while labnotes is running.\n"
)
MAX_QUEUED_EVENTS = 100_000
INVALID = {"ok": False, "error": "Invalid request"}
Queued = asyncio.Queue[tuple[str, dict[str, object]] | None]


@dataclass
class Invocation:
    """Keep controls and replayable events with one invocation's batch."""

    events: list[dict[str, object]] = field(default_factory=list)
    task: asyncio.Task[None] | None = None
    controls: Controls | None = None
    stop_requested: bool = False
    finish_up_requested: bool = False


class ExperimentDaemon:
    """Serve commands while cells run or a client remains attached."""

    def __init__(self, config: LabnotesConfig, name: str) -> None:
        self.config = config
        self.name = name
        self.active: dict[str, Invocation] = {}
        self.history: dict[str, Invocation] = {}
        self.subscribers: set[Queued] = set()
        self.starting: set[asyncio.Task[None]] = set()
        self.clients = 0
        self.closing = False
        self.last_busy = time.monotonic()
        self.start_lock = asyncio.Lock()
        self.app = Starlette(
            routes=[
                Route("/batches", self.batches),
                Route("/events", self.events),
                Route("/start", self.start_route, methods=["POST"]),
                Route("/restart", self.start_route, methods=["POST"]),
                Route("/stop", self.stop_route, methods=["POST"]),
                Route("/finish-up", self.finish_up_route, methods=["POST"]),
                Route("/concurrency", self.concurrency, methods=["POST"]),
                Route("/runs/{run}/stop", self.stop_one, methods=["POST"]),
            ]
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Count each open request, so a live stream keeps the daemon up."""
        self.clients += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.clients -= 1

    def stop_all(self) -> None:
        """Ask every invocation to stop, including one still preparing."""
        for invocation in self.active.values():
            invocation.stop_requested = True
            if invocation.controls is not None:
                invocation.controls.interrupt()

    def finish_up(self) -> None:
        """Drop queued work while active runs finish without signals."""
        for invocation in self.active.values():
            invocation.finish_up_requested = True
            if invocation.controls is not None:
                invocation.controls.finish_up()

    async def start(
        self,
        options: dict[str, object],
        progress: Callable[[str], None] = lambda step: None,
    ) -> dict[str, object]:
        """Start one invocation after earlier plans are visible."""
        if self.start_lock.locked():
            progress("Waiting for an earlier start")
        async with self.start_lock:
            return await self._start(options, progress)

    async def _start(
        self, options: dict[str, object], progress: Callable[[str], None]
    ) -> dict[str, object]:
        reserved: dict[str, dict[str, object]] = {}
        for active in self.active.values():
            events = active.events
            if any(
                event.get("event") in ("stopping", "finishing up") for event in events
            ):
                continue
            for event in events:
                if event.get("event") == "planned":
                    reserved.update(
                        {
                            str(run["run"]): cast(dict[str, object], run["params"])
                            for run in cast(list[dict[str, object]], event["runs"])
                        }
                    )
                    break
        selected = start_experiment(
            self.config,
            self.name,
            Path(str(options["experiment_config"]))
            if options.get("experiment_config") is not None
            else None,
            cast(int | None, options.get("concurrency")),
            cast(int | None, options.get("timeout")),
            cast(dict[str, list[str]] | None, options.get("only")),
            cast(list[str] | None, options.get("args")),
            cast(str | None, options.get("setup")),
            cast(str | None, options.get("teardown")),
            cast(str | None, options.get("command_line")),
            cast(str | None, options.get("run_id")),
            cast(int | None, options.get("retries")),
            cast(float | None, options.get("retry_wait")),
            bool(options.get("replace_capped")),
            reserved,
            cast(dict[str, str] | None, options.get("environment")),
            progress,
        )
        batch = selected.batch
        invocation = Invocation()
        self.active[batch] = invocation
        self.history[batch] = invocation
        ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()

        def listen(controls: Controls) -> None:
            invocation.controls = controls
            controls.finish()
            if invocation.stop_requested:
                controls.interrupt()
            elif invocation.finish_up_requested:
                controls.finish_up()
            if not ready.done():
                ready.set_result(None)

        async def run() -> None:
            try:
                await selected(lambda event: self.report(batch, event), listen)
            except Exception as error:
                if not ready.done():
                    ready.set_exception(error)
                else:
                    self.report(
                        batch,
                        stamp_event({"event": "daemon error", "error": str(error)}),
                    )
            finally:
                self.active.pop(batch, None)
                if not ready.done():
                    ready.set_exception(ValueError("Start ended before any run"))

        task = asyncio.create_task(run())
        invocation.task = task
        try:
            await ready
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "batch": batch}

    async def dispatch(
        self,
        message: dict[str, object],
        progress: Callable[[str], None] = lambda step: None,
    ) -> dict[str, object]:
        """Apply one command and provide one success or error reply."""
        action = message.get("command")
        if action in ("start", "restart"):
            options = message.get("options", {})
            if not isinstance(options, dict):
                return {"ok": False, "error": "options must be an object"}
            match action:
                case "restart" if "run_id" not in options:
                    return {"ok": False, "error": "restart needs run_id"}
            return await self.start(options, progress)
        if action == "stop_all":
            self.stop_all()
            return {"ok": True}
        if action == "finish_up":
            self.finish_up()
            return {"ok": True}
        if action == "stop_one":
            run = message.get("run")
            if not isinstance(run, str):
                return {"ok": False, "error": "stop_one needs a run id"}
            for invocation in self.active.values():
                if invocation.controls is not None:
                    invocation.controls.kill(run)
            return {"ok": True}
        if action == "set_concurrency":
            count = message.get("count")
            if not isinstance(count, int) or count < 1:
                return {"ok": False, "error": "count must be positive"}
            batch = message.get("batch")
            targets = (
                [self.active[str(batch)]]
                if batch is not None and str(batch) in self.active
                else list(self.active.values())
                if batch is None
                else []
            )
            if not targets:
                return {"ok": False, "error": "No active invocation"}
            for invocation in targets:
                if invocation.controls is not None:
                    invocation.controls.set_concurrency(count)
            return {"ok": True}
        if action == "batches":
            return {"ok": True, "batches": list(self.active)}
        return {"ok": False, "error": f"Unknown command {action}"}

    def report(self, batch: str, event: dict[str, object]) -> None:
        """Retain ordered replay and synchronously publish each stored event."""
        self.history[batch].events.append(event)
        for queue in tuple(self.subscribers):
            if queue.qsize() < MAX_QUEUED_EVENTS:
                queue.put_nowait((batch, event))
            else:
                self.subscribers.discard(queue)
                queue.put_nowait(None)

    def end_streams(self) -> None:
        for queue in self.subscribers:
            queue.put_nowait(None)
        self.subscribers.clear()

    async def answer(
        self,
        message: dict[str, object],
        progress: Callable[[str], None] = lambda step: None,
    ) -> dict[str, object]:
        try:
            return await self.dispatch(message, progress)
        except Exception as error:
            # A request always gets one error reply, even on internal failures.
            return {"ok": False, "error": str(error)}

    @staticmethod
    async def read_body(request: Request) -> dict[str, object] | None:
        try:
            body = json.loads(await request.body() or b"{}")
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    async def reply(self, message: dict[str, object]) -> Response:
        answer = await self.answer(message)
        return JSONResponse(answer, 200 if answer.get("ok") else 400)

    async def batches(self, request: Request) -> Response:
        return await self.reply({"command": "batches"})

    async def stop_route(self, request: Request) -> Response:
        return await self.reply({"command": "stop_all"})

    async def finish_up_route(self, request: Request) -> Response:
        return await self.reply({"command": "finish_up"})

    async def stop_one(self, request: Request) -> Response:
        return await self.reply({"command": "stop_one", **request.path_params})

    async def concurrency(self, request: Request) -> Response:
        body = await self.read_body(request)
        if body is None:
            return JSONResponse(INVALID, 400)
        return await self.reply({**body, "command": "set_concurrency"})

    async def start_route(self, request: Request) -> Response:
        """Stream progress steps, then the reply, as server-sent events."""
        options = await self.read_body(request)
        if options is None:
            return JSONResponse(INVALID, 400)
        message: dict[str, object] = {
            "command": request.url.path.strip("/"),
            "options": options,
        }
        updates: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

        async def run() -> None:
            answer = await self.answer(
                message, lambda step: updates.put_nowait(("step", step))
            )
            updates.put_nowait(("reply", answer))

        # A client leaving mid-start must not cancel the start.
        task = asyncio.create_task(run())
        self.starting.add(task)
        task.add_done_callback(self.starting.discard)

        async def stream() -> AsyncIterator[str]:
            while True:
                name, data = await updates.get()
                yield sse(data, name)
                if name == "reply":
                    return

        return StreamingResponse(stream(), media_type="text/event-stream")

    async def events(self, request: Request) -> Response:
        """Replay and subscribe without yielding between the snapshot and subscription."""

        async def stream() -> AsyncIterator[str]:
            queue: Queued = asyncio.Queue()
            for batch, invocation in self.history.items():
                for event in invocation.events:
                    queue.put_nowait((batch, event))
            self.subscribers.add(queue)
            try:
                yield sse({"batches": list(self.active)}, "batches")
                while (item := await queue.get()) is not None:
                    batch, event = item
                    yield sse({"batch": batch, "event": event})
            finally:
                self.subscribers.discard(queue)

        return StreamingResponse(stream(), media_type="text/event-stream")

    async def wait_until_idle(self) -> None:
        """Leave a short window for another TUI after the last cell ends."""
        while True:
            if self.closing:
                return
            if self.active or self.clients:
                self.last_busy = time.monotonic()
            elif time.monotonic() - self.last_busy >= IDLE_SECONDS:
                return
            await asyncio.sleep(0.2)


async def serve_daemon(config: LabnotesConfig, name: str) -> None:
    """Hold the experiment/version lock for one Unix server lifetime."""
    lock = lock_path(config, name)
    lock.parent.mkdir(parents=True, exist_ok=True)
    state = discovery_folder(config, name)
    state.mkdir(parents=True, exist_ok=True)
    (state.parent / "README").write_text(LIVE_STATE_NOTE)
    lock.touch(mode=0o600, exist_ok=True)
    descriptor = os.open(lock, os.O_RDONLY)
    try:
        for _ in range(10):
            try:
                fcntl.flock(descriptor, operator.or_(fcntl.LOCK_EX, fcntl.LOCK_NB))
            except BlockingIOError:
                await asyncio.sleep(0.1)
            else:
                break
        else:
            return
        path = socket_path(config, name)
        if listening(path):
            return
        path.unlink(missing_ok=True)
        daemon = ExperimentDaemon(config, name)
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(path))
        path.chmod(0o600)
        server = uvicorn.Server(
            uvicorn.Config(
                daemon,
                lifespan="off",
                log_config=None,
                access_log=False,
                timeout_graceful_shutdown=1,
            )
        )
        # startup() rather than serve(): serve() takes over SIGTERM and SIGINT.
        server.config.load()
        server.lifespan = server.config.lifespan_class(server.config)
        await server.startup(sockets=[listener])
        record = socket_record(config, name)
        pending = record.with_suffix(".socket.tmp")
        pending.write_text(str(path), encoding="utf-8")
        pending.chmod(0o600)
        pending.replace(record)
        loop = asyncio.get_running_loop()

        def close() -> None:
            daemon.closing = True
            daemon.stop_all()

        loop.add_signal_handler(signal.SIGTERM, close)
        loop.add_signal_handler(signal.SIGINT, close)
        loop.add_signal_handler(signal.SIGHUP, lambda: None)
        try:
            await daemon.wait_until_idle()
        finally:
            daemon.end_streams()
            await server.shutdown(sockets=[listener])
            daemon.stop_all()
            await asyncio.gather(
                *(item.task for item in daemon.active.values() if item.task is not None)
            )
            record.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
    finally:
        os.close(descriptor)
