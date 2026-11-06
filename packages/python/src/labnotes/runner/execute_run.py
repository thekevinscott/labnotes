import asyncio
import contextlib
import json
import os
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import psutil

from labnotes.log_path import LOG_ENV, RUN_ENV
from labnotes.runner.continue_run import continue_run
from labnotes.runner.exit_signal import exit_signal
from labnotes.runner.record_memory import record_memory
from labnotes.runner.run_git import run_git
from labnotes.runner.shell_command import shell_command
from labnotes.runner.stop_containers import stop_containers
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
    git_info: dict[str, str | bool] | None = None,
    git_diff: bytes | None = None,
    continues: bool = False,
    command_line: str | None = None,
) -> dict[str, object]:
    resolved = shell_command(command, folder, params, args)
    git = git_info if git_info is not None else await asyncio.to_thread(run_git, root)
    run: dict[str, object] = {
        "params": params,
        "command": resolved,
        "created": iso_time(time.time()),
        "ended": None,
        "exit_code": None,
        "error": None,
        "ended_by": None,
        "signal": None,
        "git": git,
        "labnotes_version": version("labnotes"),
        "labnotes_command": command_line,
    }
    if args:
        run["args"] = list(args)
    if retry_of is not None:
        run["retry_of"] = retry_of
    if meta is not None:
        run["meta"] = meta
    logs = {stream: f"{stream}.log" for stream in ("stdout", "stderr")}
    suffix = ""
    if continues:
        suffix = "-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        logs = {stream: f"{stream}{suffix}.txt" for stream in logs}
    patch = None
    if git is not None and git_diff is not None:
        patch = f"git-diff{suffix}.patch"
        (folder / f"git-sha{suffix}.txt").write_text(f"{git['commit']}\n")
        (folder / patch).write_bytes(git_diff)
    invocation: dict[str, object] | None = None
    if continues:
        invocation = {
            "started": run["created"],
            "ended": None,
            "exit_code": None,
            "ended_by": None,
            "error": None,
            "git": None if git is None else git["commit"],
            "dirty": None if git is None else git["dirty"],
            "patch": patch,
            "args": list(args),
            "labnotes_version": run["labnotes_version"],
            "labnotes_command": command_line,
            **logs,
        }
        record = folder / "run.json"
        previous = json.loads(record.read_text()) if record.exists() else {}
        run = continue_run(previous, run, invocation)
    write_run_json(folder, run)
    run_environment = os.environ if environment is None else environment
    botbox_labels = f"labnotes.run={folder.resolve()}"
    if existing_labels := run_environment.get("BOTBOX_LABELS"):
        botbox_labels = f"{existing_labels}\n{botbox_labels}"
    with (
        (folder / logs["stdout"]).open("wb") as stdout,
        (folder / logs["stderr"]).open("wb") as stderr,
    ):
        try:
            # dash doesn't exec the command, so without the trap the shell
            # dies on SIGTERM and its -15 replaces the script's own exit code.
            process = await asyncio.create_subprocess_shell(
                f"trap : TERM; {resolved}",
                cwd=root,
                env={
                    "FORCE_COLOR": "1",
                    "CLICOLOR_FORCE": "1",
                    "PYTHONUNBUFFERED": "1",
                    **{
                        key: value
                        for key, value in run_environment.items()
                        if not key.startswith("LABNOTES_")
                    },
                    LOG_ENV: str(folder / "log.jsonl"),
                    RUN_ENV: str(folder.resolve()),
                    "BOTBOX_LABELS": botbox_labels,
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
                if kill_later is not None:
                    kill_later.cancel()
                run["signal"] = exit_signal(code)
                if kill_later is not None:
                    run["ended_by"] = "timeout"
                elif stopping.is_set() or stopped():
                    run["ended_by"] = "stop"
                elif run["signal"] is not None:
                    run["ended_by"] = "signal"
                # Background jobs can outlive the shell. Once stopping, the run
                # stays killable until everything signalled is gone. A normal
                # exit ends the run even if helpers linger.
                if stopping.is_set() or kill_later is not None:
                    await wait_for_tree(tree)
                if stopping.is_set() or kill_later is not None or stopped():
                    await asyncio.to_thread(stop_containers, str(folder.resolve()))
            finally:
                if kill_later is not None:
                    kill_later.cancel()
                if sampler is not None:
                    sampler.cancel()
                    await asyncio.wait({sampler})
                running.discard(process)
    run["ended"] = iso_time(time.time())
    if invocation is not None:
        invocation |= {
            key: run[key] for key in ("ended", "exit_code", "ended_by", "error")
        }
    write_run_json(folder, run)
    return run
