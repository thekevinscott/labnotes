import asyncio
import time
from pathlib import Path

from labnotes.runner.shell_command import shell_command
from labnotes.runner.wait_for_group import wait_for_group
from labnotes.runner.write_run_json import write_run_json
from labnotes.tables.iso_time import iso_time


async def execute_run(
    root: Path,
    folder: Path,
    command: str,
    params: dict[str, object],
    running: set[asyncio.subprocess.Process],
    stopping: asyncio.Event,
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
                stdout=stdout,
                stderr=stderr,
                # Own process group, so Ctrl-C reaches labnotes first and the
                # runner decides how each run stops.
                start_new_session=True,
            )
        except OSError as error:
            run["error"] = str(error)
        else:
            running.add(process)
            try:
                run["exit_code"] = await process.wait()
                # The shell can exit on SIGTERM before what it started. Once
                # stopping, the run stays killable until its whole group is
                # gone. A normal exit ends the run even if helpers linger.
                if stopping.is_set():
                    await wait_for_group(process.pid)
            finally:
                running.discard(process)
    run["ended"] = iso_time(time.time())
    write_run_json(folder, run)
    return run
