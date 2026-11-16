"""Throwaway spike for #491: drive one labnotes-style cell through a private pueued.

Run state stays in the run folder (run.json, stdout.log, stderr.log). pueue only
owns the process. Every command is stateless: a fresh Python process can adopt a
cell another one started, by reading run.json and `pueue status --json`.

    uv run --no-project python cell.py daemon
    uv run --no-project python cell.py start <folder> -- <command>
    uv run --no-project python cell.py stop <folder>
    uv run --no-project python cell.py restart <folder>
    uv run --no-project python cell.py reconcile <folder>
    uv run --no-project python cell.py shutdown
"""

import json
import os
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HOME = Path(os.environ.get("PUEUE_SPIKE_DIR", "/tmp/claude/pueue-spike-491/proto"))
BIN = Path(os.environ.get("PUEUE_BIN", "/tmp/claude/pueue-spike-491/bin"))
CONFIG = HOME / "pueue.yml"
GROUP = "cells"
GRACE_SECONDS = 5


def now() -> str:
    return datetime.now(UTC).isoformat()


def pueue(*args: str) -> str:
    result = subprocess.run(
        [str(BIN / "pueue"), "-c", str(CONFIG), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def tasks() -> dict[str, dict]:
    return json.loads(pueue("status", "--json"))["tasks"]


def daemon() -> None:
    """Start a private pueued (own config, socket, state) unless one answers."""
    for sub in ("state", "run"):
        (HOME / sub).mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(
        "shared:\n"
        f"  pueue_directory: {HOME / 'state'}\n"
        f"  runtime_directory: {HOME / 'run'}\n"
        "  use_unix_socket: true\n"
        f"  unix_socket_path: {HOME / 'run' / 'pueue.sock'}\n"
        f"  pid_path: {HOME / 'run' / 'pueue.pid'}\n"
        f"  alias_file: {HOME / 'state' / 'aliases.yml'}\n"
        "client:\n  show_confirmation_questions: false\n"
        "daemon:\n  pause_group_on_failure: false\n  pause_all_on_failure: false\n"
    )
    try:
        pueue("status", "--json")
    except subprocess.CalledProcessError:
        subprocess.run([str(BIN / "pueued"), "-c", str(CONFIG), "-d"], check=True)
        time.sleep(0.5)
    if GROUP not in json.loads(pueue("status", "--json"))["groups"]:
        pueue("group", "add", GROUP, "-p", "2")


def read_run(folder: Path) -> dict:
    return json.loads((folder / "run.json").read_text())


def write_run(folder: Path, run: dict) -> None:
    partial = folder / f"run.json.{os.getpid()}.tmp"
    partial.write_text(json.dumps(run, indent=2) + "\n")
    partial.replace(folder / "run.json")


def enqueue(folder: Path, command: str) -> int:
    # pid: the process-group leader, for memory sampling. The trap keeps sh
    # alive through the group-wide SIGTERM so the cell's own exit code wins.
    wrapped = f"echo $$ > pid; exec >stdout.log 2>stderr.log; trap : TERM; {command}"
    out = pueue(
        "add", "--print-task-id", "-g", GROUP, "-l", str(folder),
        "-w", str(folder), "--", wrapped,
    )
    return int(out.strip())


def start(folder: Path, command: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    task = enqueue(folder, command)
    write_run(
        folder,
        {"command": command, "created": now(), "ended": None, "exit_code": None,
         "ended_by": None, "pueue_task": task},
    )
    print(f"started {folder} as pueue task {task}")


def stop(folder: Path) -> None:
    run = read_run(folder)
    task = str(run["pueue_task"])
    run["stop_requested"] = now()
    write_run(folder, run)
    pueue("kill", "-s", "term", task)
    deadline = time.monotonic() + GRACE_SECONDS
    while time.monotonic() < deadline:
        if "Done" in tasks()[task]["status"]:
            break
        time.sleep(0.2)
    else:
        pueue("kill", task)
    reconcile(folder)


def restart(folder: Path) -> None:
    run = read_run(folder)
    if run["ended"] is None:
        stop(folder)
        run = read_run(folder)
    history = run.pop("invocations", [])
    history.append({k: run[k] for k in ("pueue_task", "created", "ended", "exit_code", "ended_by")})
    task = enqueue(folder, run["command"])
    write_run(
        folder,
        {**run, "invocations": history, "created": now(), "ended": None,
         "exit_code": None, "ended_by": None, "pueue_task": task,
         "stop_requested": None},
    )
    print(f"restarted {folder} as pueue task {task}")


def reconcile(folder: Path) -> dict:
    """Fold pueue's view of the task into run.json. Replaces mark_lost."""
    run = read_run(folder)
    if run["ended"] is not None:
        return run
    task = tasks().get(str(run["pueue_task"]))
    if task is None or task.get("label") != str(folder):
        run |= {"ended": now(), "ended_by": "lost"}
    elif "Done" in task["status"]:
        done = task["status"]["Done"]
        result = done["result"]
        run["ended"] = done["end"]
        if result == "Success":
            run["exit_code"] = 0
        elif isinstance(result, dict) and "Failed" in result:
            run["exit_code"] = result["Failed"]
        if run.get("stop_requested"):
            run["ended_by"] = "stop"
        elif result == "Killed":
            run["ended_by"] = "killed"
        else:
            run["ended_by"] = None if run["exit_code"] is not None else str(result)
    else:
        print(f"{folder}: adopted, pueue says {next(iter(task['status']))}")
        return run
    write_run(folder, run)
    print(f"{folder}: ended_by={run['ended_by']} exit_code={run['exit_code']}")
    return run


def shutdown() -> None:
    pid = int((HOME / "run" / "pueue.pid").read_text())
    os.kill(pid, 15)


def main() -> None:
    cmd, *rest = sys.argv[1:]
    match cmd:
        case "daemon":
            daemon()
        case "start":
            folder, _, *command = rest
            start(Path(folder).resolve(), shlex.join(command) if len(command) > 1 else command[0])
        case "stop":
            stop(Path(rest[0]).resolve())
        case "restart":
            restart(Path(rest[0]).resolve())
        case "reconcile":
            reconcile(Path(rest[0]).resolve())
        case "shutdown":
            shutdown()


if __name__ == "__main__":
    main()
