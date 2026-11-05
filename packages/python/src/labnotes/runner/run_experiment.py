import asyncio
import json
import os
import signal
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil

from labnotes.models import (
    Controls,
    ExperimentConfig,
    LabnotesConfig,
    Listen,
    Report,
)
from labnotes.retries import RETRY_EXIT_CODE
from labnotes.runner.check_hook_placeholders import check_hook_placeholders
from labnotes.runner.claim_run import LOCK_FILE, claim_run
from labnotes.runner.execute_run import execute_run
from labnotes.runner.fill_experiment_env import fill_experiment_env
from labnotes.runner.fill_dirs import fill_dirs
from labnotes.runner.in_subset import in_subset
from labnotes.runner.invocation_hook import invocation_hook
from labnotes.runner.invocation_meta import invocation_meta
from labnotes.runner.new_stamped_run_id import new_stamped_run_id
from labnotes.runner.param_grid import param_grid
from labnotes.runner.placeholders import PLACEHOLDERS
from labnotes.runner.plan_runs import plan_runs
from labnotes.runner.project_snapshot import ProjectSnapshot
from labnotes.runner.run_folder import run_folder
from labnotes.runner.run_locked import run_locked
from labnotes.runner.run_state import RunState
from labnotes.runner.signal_tree import signal_tree
from labnotes.state_path import STATE_ENV
from labnotes.tables.experiment_run_ids import experiment_run_ids
from labnotes.tables.list_experiment_runs import list_experiment_runs
from labnotes.tables.list_resumable_runs import list_resumable_runs
from labnotes.tables.open_tables import open_tables

Entry = tuple[str, dict[str, object]]


async def run_experiment(
    config: LabnotesConfig,
    name: str,
    experiment: ExperimentConfig,
    concurrency: int,
    report: Report,
    listen: Listen,
    timeout: float | None = None,
    only: dict[str, list[str]] | None = None,
    args: list[str] | None = None,
    environment: dict[str, str] | None = None,
    snapshot: ProjectSnapshot | None = None,
    command_line: str | None = None,
    run_id: str | None = None,
    run_state: RunState | None = None,
    reserved: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    state = run_state or RunState.create(config, name)
    forward = report

    def emit(event: dict[str, object]) -> None:
        state.record(event)
        forward(event)

    command_root = snapshot.root if snapshot is not None else config.root
    inherited = dict(os.environ) if environment is None else environment
    tables = open_tables(config)
    existing = await experiment_run_ids(tables, name)
    counted = await list_experiment_runs(tables, name, experiment.counts)
    held = [
        r
        for r in counted
        if not r["counted"]
        and r.get("folder") is not None
        and (config.root / str(r["folder"]) / LOCK_FILE).exists()
        and run_locked(config.root / str(r["folder"]))
    ]
    held_ids = {str(r["id"]) for r in held}
    finished = [
        params for run, params in (reserved or {}).items() if run not in existing
    ]
    finished += [
        json.loads(str(r["params"]))
        for r in counted
        if r["counted"] or str(r.get("id")) in held_ids
    ]
    resumable: list[Entry] = []
    capped: list[Entry] = []
    tries: dict[str, int] = {}
    if experiment.continues:
        for row in await list_resumable_runs(tables, name, experiment.counts):
            entry = (str(row["id"]), json.loads(str(row["params"])))
            tries[entry[0]] = int(str(row["invocations"]))
            over = tries[entry[0]] > experiment.retries
            (capped if over else resumable).append(entry)
    if not experiment.replace_capped:
        finished += [params for _, params in capped]
    planned: set[str] = set()

    def taken(run: str) -> bool:
        return run in planned or run in existing

    if run_id is None:
        grid = [
            cell
            for cell in param_grid(experiment.params)
            if in_subset(cell, only or {})
        ]
        cells = plan_runs(grid, experiment.repeats, finished)
    else:
        cells = []

    locks: dict[str, int] = {}

    def claim(run: str) -> bool:
        if run not in locks:
            lock = claim_run(run_folder(config.root, config.runs, name, run))
            if lock is None:
                return False
            locks[run] = lock
        return True

    def release(run: str) -> None:
        os.close(locks.pop(run))

    plan: list[Entry] = []
    target_folder: Path | None = None
    if run_id is not None:
        selected = next((row for row in counted if row["id"] == run_id), None)
        if selected is None:
            raise ValueError(f"No run {run_id} in {name}.")
        if selected["ended"] is None or (
            selected["exit_code"] == 0 and not selected["error"]
        ):
            raise ValueError(f"Run {run_id} has not failed.")
        source = config.root / str(selected["folder"])
        record = json.loads((source / "run.json").read_text())
        args = record.get("args", [])
        params = json.loads(str(selected["params"]))
        lock = claim_run(source)
        if lock is None:
            raise ValueError(f"Run {run_id} is held by another run.")
        locks[run_id] = lock
        if experiment.continues:
            target_folder = source
            plan.append((run_id, params))
        else:
            new_id = new_stamped_run_id(taken)
            planned.add(new_id)
            plan.append((new_id, params))
    for params in cells:
        resumed = next(
            (
                entry
                for entry in resumable
                if entry[1] == params and entry[0] not in planned and claim(entry[0])
            ),
            None,
        )
        run = new_stamped_run_id(taken) if resumed is None else resumed[0]
        planned.add(run)
        plan.append((run, params))
    # A resumed run's earlier invocations spend the same retries as exit 75 does.
    earlier = {run: tries[run] for run, _ in plan if run in tries and run != run_id}
    hooks = {
        "setup": experiment.setup,
        "teardown": experiment.teardown,
        "meta": experiment.meta,
    }
    check_hook_placeholders(hooks)
    hook_env = {
        hook: fill_experiment_env(experiment.env, inherited, {})
        for hook, command in hooks.items()
        if command is not None
    }
    meta = None
    if experiment.meta is not None:
        meta = await invocation_meta(command_root, experiment.meta, hook_env["meta"])
    runs = [{"run": run, "params": params} for run, params in plan]
    emit(
        {
            "event": "planned",
            "title": experiment.name or name,
            "runs": runs,
            "concurrency": concurrency,
        }
    )
    for row in held:
        emit({"event": "held", "run": str(row["id"])})
    gave_up = [run for run, params in capped if in_subset(params, only or {})]
    if gave_up and run_id is None and not experiment.replace_capped:
        emit({"event": "capped", "runs": gave_up, "retries": experiment.retries})
    running: dict[str, set[asyncio.subprocess.Process]] = {}
    trees: dict[str, set[psutil.Process]] = {}
    stopped: set[str] = set()
    results: dict[str, dict[str, object]] = {}
    stopping = asyncio.Event()

    def signal_run(run: str, signal_number: int) -> None:
        for process in running[run]:
            signal_tree(process.pid, signal_number, trees[run])

    def signal_runs(signal_number: int) -> None:
        for run in running:
            signal_run(run, signal_number)

    def interrupt() -> None:
        plan.clear()
        if not stopping.is_set():
            stopping.set()
            emit({"event": "stopping"})
            signal_runs(signal.SIGTERM)
            if waiting:
                for run in list(waiting):
                    cancel_retry(run)
                fill()
        elif any(running.values()):
            emit({"event": "killing"})
            signal_runs(signal.SIGKILL)

    def kill(run: str) -> None:
        if run in waiting:
            cancel_retry(run)
            fill()
            return
        if not running.get(run):
            return
        if run in stopped:
            emit({"event": "killing run", "run": run})
            signal_run(run, signal.SIGKILL)
        else:
            stopped.add(run)
            emit({"event": "stopping run", "run": run})
            signal_run(run, signal.SIGTERM)

    ended: dict[str, dict[str, object]] = {}
    parents: dict[str, str] = {}
    attempts: dict[str, int] = {}
    waiting: dict[str, asyncio.TimerHandle] = {}

    def requeue(run: str, attempt: int) -> None:
        again = run
        if not experiment.continues:
            again = new_stamped_run_id(taken)
            planned.add(again)
            parents[again] = run
        attempts[again] = attempt
        plan.append((again, ended[run]))
        emit({"event": "retried", "run": run, "retry": again, "params": ended[run]})
        fill()

    def retry_later(run: str) -> None:
        tried = attempts.get(run, earlier.get(run, 0))
        if tried >= experiment.retries:
            emit({"event": "gave up", "run": run, "retries": tried})
            return
        seconds = experiment.retry_wait * 2 ** (tried - earlier.get(run, 0))

        def due() -> None:
            del waiting[run]
            requeue(run, tried + 1)

        waiting[run] = asyncio.get_running_loop().call_later(seconds, due)
        emit(
            {
                "event": "retrying",
                "run": run,
                "attempt": tried + 1,
                "retries": experiment.retries,
                "seconds": seconds,
            }
        )

    def cancel_retry(run: str) -> None:
        waiting.pop(run).cancel()
        release(run)
        emit({"event": "retry cancelled", "run": run})

    limit = concurrency
    live: set[asyncio.Task[None]] = set()
    started: list[asyncio.Task[None]] = []
    finishing = False
    done = asyncio.Event()

    def fill() -> None:
        while plan and len(live) < limit:
            task = asyncio.create_task(start(*plan.pop(0)))
            task.add_done_callback(end)
            live.add(task)
            started.append(task)
        if not (live or waiting):
            emit({"event": "idle"})
            if finishing:
                done.set()

    def finish() -> None:
        nonlocal finishing
        finishing = True
        if not (live or plan or waiting):
            done.set()

    def end(task: asyncio.Task[None]) -> None:
        live.remove(task)
        fill()

    def set_concurrency(count: int) -> None:
        nonlocal limit
        limit = max(1, count)
        emit({"event": "concurrency", "concurrency": limit})
        fill()

    async def start(run: str, params: dict[str, object]) -> None:
        folder = target_folder or run_folder(config.root, config.runs, name, run)
        folder.mkdir(parents=True, exist_ok=True)
        if not claim(run):
            emit({"event": "held", "run": run})
            return
        if snapshot is not None and snapshot.sha is not None:
            (folder / "git-sha.txt").write_text(snapshot.sha + "\n")
            (folder / "git-diff.patch").write_bytes(snapshot.diff or b"")
        emit({"event": "started", "run": run, "params": params, "folder": folder})
        # {invocation_dir} stays for configs written before runs were flat.
        dirs = dict.fromkeys(PLACEHOLDERS, str(folder.resolve()))
        running[run] = set()
        trees[run] = set()
        result = await execute_run(
            command_root,
            folder,
            fill_dirs(
                experiment.command,
                dirs,
            ),
            params,
            running[run],
            stopping,
            trees[run],
            parents.get(run),
            timeout=timeout,
            stop=lambda: kill(run),
            stopped=lambda: run in stopped,
            meta=meta,
            args=args or (),
            state_file=state_file,
            memory_interval=experiment.memory_interval,
            environment=fill_experiment_env(
                experiment.env,
                inherited,
                dirs,
            ),
            git_info=(
                {"commit": snapshot.sha, "dirty": bool(snapshot.diff)}
                if snapshot is not None and snapshot.sha is not None
                else None
            ),
            continues=experiment.continues,
            command_line=command_line,
        )
        del running[run], trees[run]
        emit({"event": "ended", "run": run, **result})
        ended[run] = params
        results[run] = {"run": run, **result}
        if result["exit_code"] == RETRY_EXIT_CODE and not (
            stopping.is_set() or run in stopped
        ):
            retry_later(run)
        if run not in waiting:
            release(run)

    async def teardown() -> None:
        if experiment.teardown is not None:
            emit({"event": "tearing down"})
            await invocation_hook(
                command_root,
                "teardown",
                experiment.teardown,
                hook_env["teardown"],
            )

    listen(Controls(interrupt, set_concurrency, kill, finish))
    with TemporaryDirectory(prefix="labnotes-state-") as state_dir:
        state_file = Path(state_dir) / "state.json"
        for hook in ("setup", "teardown"):
            if hook in hook_env:
                hook_env[hook][STATE_ENV] = str(state_file)
        # Like vitest's globalSetup: a failed setup still gets its teardown.
        try:
            if experiment.setup is not None:
                emit({"event": "setting up"})
                await invocation_hook(
                    command_root,
                    "setup",
                    experiment.setup,
                    hook_env["setup"],
                )
            fill()
            await done.wait()
            await asyncio.gather(*started)
        except BaseException:
            try:
                await teardown()
            except Exception as failure:  # noqa: BLE001
                emit({"event": "teardown failed", "error": str(failure)})
            raise
        finally:
            for run in list(locks):
                release(run)
        await teardown()
        if experiment.teardown is not None:
            emit({"event": "idle"})
    return list(results.values())
