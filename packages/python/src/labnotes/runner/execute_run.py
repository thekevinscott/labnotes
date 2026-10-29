import asyncio
import contextlib
import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import psutil

from labnotes.log_path import LOG_ENV, RUN_ENV
from labnotes.runner.exit_signal import exit_signal
from labnotes.runner.record_memory import record_memory
from labnotes.runner.run_git import run_git
from labnotes.runner.shell_command import shell_command
from labnotes.runner.stop_then_kill import GRACE_SECONDS
from labnotes.runner.wait_for_tree import wait_for_tree
from labnotes.runner.write_run_json import write_run_json
from labnotes.state_path import RUN_STATE_ENV
from labnotes.tables.iso_time import iso_time
from labnotes.tui.format_elapsed import format_elapsed


async def execute_run(
    root: Path,
    folder: Path,
    command: str,
    params: dict[str, object],
    running: set[asyncio.subprocess.Process],
    stopping: asyncio.Event,
    tree: set[psutil.Process],
    retry_of: str | None = None,
    timeout: float | None = None,
    stop: Callable[[], None] = lambda: None,
    stopped: Callable[[], bool] = lambda: False,
    meta: dict[str, object] | None = None,
    args: Sequence[str] = (),
    *,
    state_file: Path,
    memory_interval: float,
    environment: dict[str, str] | None = None,
) -> dict[str, object]:
    resolved = shell_command(command, folder, params, args)
    run: dict[str, object] = {
        "params": params,
        "command": resolved,
        "created": iso_time(time.time()),
        "ended": None,
        "exit_code": None,
        "error": None,
        "ended_by": None,
        "signal": None,
        "git": await asyncio.to_thread(run_git, root),
    }
    if args:
        run["args"] = list(args)
    if retry_of is not None:
        run["retry_of"] = retry_of
    if meta is not None:
        run["meta"] = meta
    write_run_json(folder, run)
    with (
        (folder / "stdout.log").open("wb") as stdout,
        (folder / "stderr.log").open("wb") as stderr,
    ):
        try:
            process = await asyncio.create_subprocess_shell(
                resolved,
                cwd=root,
                env={
                    "FORCE_COLOR": "1",
                    "CLICOLOR_FORCE": "1",
                    **{
                        key: value
                        for key, value in (
                            os.environ if environment is None else environment
                        ).items()
                        if not key.startswith("LABNOTES_")
                    },
                    LOG_ENV: str(folder / "log.jsonl"),
                    RUN_ENV: str(folder.resolve()),
                    RUN_STATE_ENV: str(state_file),
                },
                stdout=stdout,
                stderr=stderr,
            )
        except OSError as error:
            run["error"] = str(error)
        else:
            running.add(process)
            run["pid"] = process.pid
            created = None
            with contextlib.suppress(psutil.Error):
                run["pid_created"] = created = psutil.Process(process.pid).create_time()
            write_run_json(folder, run)
            sampler = None
            if memory_interval > 0 and created is not None:
                sampler = asyncio.create_task(
                    record_memory(
                        folder / "memory.jsonl", process.pid, created, memory_interval
                    )
                )
            exited = asyncio.ensure_future(process.wait())
            kill_later = None
            try:
                if (
                    timeout is not None
                    and not (await asyncio.wait({exited}, timeout=timeout))[0]
                ):
                    run["error"] = f"timed out after {format_elapsed(timeout)}"
                    stop()
                    kill_later = asyncio.get_running_loop().call_later(
                        GRACE_SECONDS, stop
                    )
                run["exit_code"] = code = await exited
                run["signal"] = exit_signal(code)
                if kill_later is not None:
                    run["ended_by"] = "timeout"
                elif stopping.is_set() or stopped():
                    run["ended_by"] = "stop"
                elif run["signal"] is not None:
                    run["ended_by"] = "signal"
                # The shell can exit on SIGTERM before what it started. Once
                # stopping, the run stays killable until everything signalled
                # is gone. A normal exit ends the run even if helpers linger.
                if stopping.is_set() or kill_later is not None:
                    await wait_for_tree(tree)
            finally:
                if kill_later is not None:
                    kill_later.cancel()
                if sampler is not None:
                    sampler.cancel()
                    await asyncio.wait({sampler})
                running.discard(process)
    run["ended"] = iso_time(time.time())
    write_run_json(folder, run)
    return run
