import asyncio
import shlex
import time
from pathlib import Path

from labnotes.runner.param_args import param_args
from labnotes.runner.write_run_json import write_run_json
from labnotes.tables.iso_time import iso_time


async def execute_run(
    folder: Path,
    command: str,
    params: dict[str, object],
    running: set[asyncio.subprocess.Process],
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
                f"{command} {shlex.join(param_args(params))}".rstrip(),
                cwd=folder,
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
            finally:
                running.discard(process)
    run["ended"] = iso_time(time.time())
    write_run_json(folder, run)
    return run
