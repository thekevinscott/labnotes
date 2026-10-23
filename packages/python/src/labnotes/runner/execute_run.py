import asyncio
import contextlib
import os
import time
from collections.abc import Callable
from pathlib import Path

import psutil

from labnotes.log_path import LOG_ENV
from labnotes.runner.shell_command import shell_command
from labnotes.runner.stop_then_kill import GRACE_SECONDS
from labnotes.runner.wait_for_tree import wait_for_tree
from labnotes.runner.write_run_json import write_run_json
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
) -> dict[str, object]:
    run: dict[str, object] = {
        "params": params,
        "created": iso_time(time.time()),
        "ended": None,
        "exit_code": None,
        "error": None,
    }
    if retry_of is not None:
        run["retry_of"] = retry_of
    write_run_json(folder, run)
    with (
        (folder / "stdout.log").open("wb") as stdout,
        (folder / "stderr.log").open("wb") as stderr,
    ):
        try:
            process = await asyncio.create_subprocess_shell(
                shell_command(command, folder, params),
                cwd=root,
                env={
                    "FORCE_COLOR": "1",
                    "CLICOLOR_FORCE": "1",
                    **os.environ,
                    LOG_ENV: str(folder / "log.jsonl"),
                },
                stdout=stdout,
                stderr=stderr,
            )
        except OSError as error:
            run["error"] = str(error)
        else:
            running.add(process)
            run["pid"] = process.pid
            with contextlib.suppress(psutil.Error):
                run["pid_created"] = psutil.Process(process.pid).create_time()
            write_run_json(folder, run)
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
                run["exit_code"] = await exited
                # The shell can exit on SIGTERM before what it started. Once
                # stopping, the run stays killable until everything signalled
                # is gone. A normal exit ends the run even if helpers linger.
                if stopping.is_set() or kill_later is not None:
                    await wait_for_tree(tree)
            finally:
                if kill_later is not None:
                    kill_later.cancel()
                running.discard(process)
    run["ended"] = iso_time(time.time())
    write_run_json(folder, run)
    return run
