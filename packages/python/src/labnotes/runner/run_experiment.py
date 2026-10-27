import asyncio
import json
import signal

import psutil

from labnotes.models import (
    Controls,
    ExperimentConfig,
    LabnotesConfig,
    Listen,
    Report,
)
from labnotes.retries import RETRY_EXIT_CODE, RETRY_SECONDS
from labnotes.runner.execute_run import execute_run
from labnotes.runner.in_subset import in_subset
from labnotes.runner.invocation_meta import invocation_meta
from labnotes.runner.new_param_run_id import new_param_run_id
from labnotes.runner.new_stamped_run_id import new_stamped_run_id
from labnotes.runner.param_grid import param_grid
from labnotes.runner.plan_runs import plan_runs
from labnotes.runner.run_folder import run_folder
from labnotes.runner.signal_tree import signal_tree
from labnotes.tables.experiment_run_ids import experiment_run_ids
from labnotes.tables.list_experiment_runs import list_experiment_runs
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
    retry_seconds: float = RETRY_SECONDS,
    only: dict[str, str] | None = None,
    args: list[str] | None = None,
) -> list[dict[str, object]]:
    meta = None
    if experiment.meta is not None:
        meta = await invocation_meta(config.root, experiment.meta)
    tables = open_tables(config)
    existing = await experiment_run_ids(tables, name)
    finished: list[dict[str, object]] = []
    match experiment.mode:
        case "matrix":
            counted = await list_experiment_runs(tables, name, experiment.counts)
            finished = [json.loads(str(r["params"])) for r in counted if r["counted"]]
    planned: set[str] = set()

    def taken(run: str) -> bool:
        return run in planned or run in existing

    grid = [
        cell for cell in param_grid(experiment.params) if in_subset(cell, only or {})
    ]
    cells = plan_runs(grid, experiment.repeats, finished)
    group = None
    match experiment.mode:
        case "adhoc" if len(cells) > 1:
            group = new_stamped_run_id(taken)

    def new_id(params: dict[str, object]) -> str:
        if group is None:
            return new_stamped_run_id(taken)
        return f"{group}/" + new_param_run_id(
            params, experiment.params, lambda run: taken(f"{group}/{run}")
        )

    plan: list[Entry] = []
    for params in cells:
        run = new_id(params)
        planned.add(run)
        plan.append((run, params))
    runs = [{"run": run, "params": params} for run, params in plan]
    report(
        {
            "event": "planned",
            "title": experiment.name or name,
            "runs": runs,
            "concurrency": concurrency,
            "mode": experiment.mode,
        }
    )
    running: dict[str, set[asyncio.subprocess.Process]] = {}
    trees: dict[str, set[psutil.Process]] = {}
    stopped: set[str] = set()
    results: list[dict[str, object]] = []
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
            report({"event": "stopping"})
            signal_runs(signal.SIGTERM)
            if waiting:
                for run in list(waiting):
                    cancel_retry(run)
                fill()
        elif any(running.values()):
            report({"event": "killing"})
            signal_runs(signal.SIGKILL)

    def kill(run: str) -> None:
        if run in waiting:
            cancel_retry(run)
            fill()
            return
        if not running.get(run):
            return
        if run in stopped:
            report({"event": "killing run", "run": run})
            signal_run(run, signal.SIGKILL)
        else:
            stopped.add(run)
            report({"event": "stopping run", "run": run})
            signal_run(run, signal.SIGTERM)

    ended: dict[str, dict[str, object]] = {}
    parents: dict[str, str] = {}
    attempts: dict[str, int] = {}
    waiting: dict[str, asyncio.TimerHandle] = {}

    def requeue(run: str, attempt: int) -> None:
        again = new_id(ended[run])
        planned.add(again)
        parents[again] = run
        attempts[again] = attempt
        plan.append((again, ended[run]))
        report({"event": "retried", "run": run, "retry": again, "params": ended[run]})
        fill()

    def retry_later(run: str) -> None:
        tried = attempts.get(run, 0)
        if tried >= experiment.retries:
            report({"event": "gave up", "run": run, "retries": tried})
            return
        seconds = retry_seconds * 2**tried

        def due() -> None:
            del waiting[run]
            requeue(run, tried + 1)

        waiting[run] = asyncio.get_running_loop().call_later(seconds, due)
        report(
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
        report({"event": "retry cancelled", "run": run})

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
            report({"event": "idle"})
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
        report({"event": "concurrency", "concurrency": limit})
        fill()

    async def start(run: str, params: dict[str, object]) -> None:
        folder = run_folder(config.root, config.runs, name, run)
        folder.mkdir(parents=True)
        report({"event": "started", "run": run, "params": params, "folder": folder})
        running[run] = set()
        trees[run] = set()
        result = await execute_run(
            config.root,
            folder,
            experiment.command,
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
            memory_interval=experiment.memory_interval,
        )
        del running[run], trees[run]
        report({"event": "ended", "run": run, **result})
        ended[run] = params
        results.append(result)
        if result["exit_code"] == RETRY_EXIT_CODE and not (
            stopping.is_set() or run in stopped
        ):
            retry_later(run)

    listen(Controls(interrupt, set_concurrency, kill, finish))
    fill()
    await done.wait()
    await asyncio.gather(*started)
    return results
