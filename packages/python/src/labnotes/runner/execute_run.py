import asyncio
import os
import time
from pathlib import Path

import psutil

from labnotes.log_path import LOG_ENV
from labnotes.runner.shell_command import shell_command
from labnotes.runner.wait_for_tree import wait_for_tree
from labnotes.runner.write_run_json import write_run_json
from labnotes.tables.iso_time import iso_time


async def execute_run(
    root: Path,
    folder: Path,
    command: str,
    params: dict[str, object],
    running: set[asyncio.subprocess.Process],
    stopping: asyncio.Event,
    tree: set[psutil.Process],
) -> dict[str, object]:
    run: dict[str, object] = {
        "params": params,
        "created": iso_time(time.time()),
        "ended": None,
        "exit_code": None,
        "error": None,
    }
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
            try:
                run["exit_code"] = await process.wait()
                # The shell can exit on SIGTERM before what it started. Once
                # stopping, the run stays killable until everything signalled
                # is gone. A normal exit ends the run even if helpers linger.
                if stopping.is_set():
                    await wait_for_tree(tree)
            finally:
                running.discard(process)
    run["ended"] = iso_time(time.time())
    write_run_json(folder, run)
    return run
