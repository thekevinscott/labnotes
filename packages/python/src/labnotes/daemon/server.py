"""Own experiment invocations behind a private request/response socket."""

import asyncio
import fcntl
import json
import os
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from labnotes.daemon.socket_path import lock_path, socket_path, socket_record
from labnotes.models import Controls, LabnotesConfig
from labnotes.runner.start_experiment import start_experiment

IDLE_SECONDS = 5.0


@dataclass
class Invocation:
    """Keep controls with the one invocation that produced a journal."""

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
        self.clients = 0
        self.closing = False
        self.last_busy = time.monotonic()
        self.start_lock = asyncio.Lock()

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
        for path in self.active:
            try:
                events = [
                    json.loads(line) for line in Path(path).read_text().splitlines()
                ]
            except FileNotFoundError:
                continue
            if any(
                event.get("event") in ("stopping", "finishing up") for event in events
            ):
                continue
            for event in events:
                if event.get("event") == "planned":
                    reserved.update(
                        {
                            str(run["run"]): cast(dict[str, object], run["params"])
                            for run in event["runs"]
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
        path = str(selected.run_state.path)
        invocation = Invocation()
        self.active[path] = invocation
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
                await selected(lambda event: None, listen)
            except Exception as error:
                if not ready.done():
                    ready.set_exception(error)
                else:
                    selected.run_state.record(
                        {"event": "daemon error", "error": str(error)}
                    )
            finally:
                self.active.pop(path, None)
                if not ready.done():
                    ready.set_exception(ValueError("Start ended before any run"))

        task = asyncio.create_task(run())
        invocation.task = task
        try:
            await ready
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "journal": path}

    async def dispatch(
        self,
        message: dict[str, object],
        progress: Callable[[str], None] = lambda step: None,
    ) -> dict[str, object]:
        """Apply one command and provide one success or error reply."""
        action = message.get("command")
        if action == "ping":
            return {"ok": True}
        if action in ("start", "restart"):
            options = message.get("options", {})
            if not isinstance(options, dict):
                return {"ok": False, "error": "options must be an object"}
            if action == "restart" and "run_id" not in options:  # probe
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
            journal = message.get("journal")
            targets = (
                [self.active[str(journal)]]
                if journal is not None and str(journal) in self.active
                else list(self.active.values())
                if journal is None
                else []
            )
            if not targets:
                return {"ok": False, "error": "No active invocation"}
            for invocation in targets:
                if invocation.controls is not None:
                    invocation.controls.set_concurrency(count)
            return {"ok": True}
        if action == "attach":
            return {"ok": True}
        return {"ok": False, "error": f"Unknown command {action}"}

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Hold an attach connection open without streaming events to it."""
        self.clients += 1
        try:
            line = await reader.readline()
            if not line:
                return
            message = json.loads(line)
            if not isinstance(message, dict):
                reply = {"ok": False, "error": "Request must be an object"}
            else:
                try:
                    reply = await self.dispatch(
                        message,
                        lambda step: writer.write(
                            (json.dumps({"step": step}) + "\n").encode()
                        ),
                    )
                except Exception as error:
                    # A request always gets one error reply, even on internal failures.
                    reply = {"ok": False, "error": str(error)}
            writer.write((json.dumps(reply) + "\n").encode())
            await writer.drain()
            if isinstance(message, dict) and message.get("command") == "attach":
                await reader.read()
        except (json.JSONDecodeError, asyncio.LimitOverrunError):
            writer.write(b'{"ok":false,"error":"Invalid request"}\n')
            await writer.drain()
        finally:
            self.clients -= 1
            writer.close()
            await writer.wait_closed()

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
    lock.touch(mode=0o600, exist_ok=True)
    descriptor = os.open(lock, os.O_RDONLY)
    try:
        for _ in range(10):
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)  # probe
            except BlockingIOError:
                await asyncio.sleep(0.1)
            else:
                break
        else:
            return
        path = socket_path(config, name)
        path.unlink(missing_ok=True)
        daemon = ExperimentDaemon(config, name)
        server = await asyncio.start_unix_server(daemon.handle, path=str(path))
        path.chmod(0o600)
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
            server.close()
            await server.wait_closed()
            daemon.stop_all()
            await asyncio.gather(
                *(item.task for item in daemon.active.values() if item.task is not None)
            )
            record.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
    finally:
        os.close(descriptor)
