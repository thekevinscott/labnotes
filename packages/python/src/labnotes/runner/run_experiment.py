import asyncio
import contextlib
import json
import os
import signal

from labnotes.models import (
    Controls,
    ExperimentConfig,
    LabnotesConfig,
    Listen,
    Report,
)
from labnotes.runner.execute_run import execute_run
from labnotes.runner.new_invocation_id import new_invocation_id
from labnotes.runner.new_run_id import new_run_id
from labnotes.runner.param_grid import param_grid
from labnotes.runner.plan_runs import plan_runs
from labnotes.runner.run_folder import run_folder
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
) -> list[dict[str, object]]:
    finished: list[dict[str, object]] = []
    match experiment.mode:
        case "fill":
            tables = open_tables(config)
            existing = await list_experiment_runs(tables, name, experiment.counts)
            finished = [json.loads(str(r["params"])) for r in existing if r["counted"]]
    planned: set[str] = set()

    def taken(run: str) -> bool:
        return (
            run in planned or run_folder(config.root, config.runs, name, run).exists()
        )

    invocation = new_invocation_id()
    plan: list[Entry] = []
    for params in plan_runs(
        param_grid(experiment.params), experiment.repeats, finished
    ):
        run = new_run_id(taken)
        planned.add(run)
        plan.append((run, params))
    runs = [{"run": run, "params": params} for run, params in plan]
    report(
        {
            "event": "planned",
            "runs": runs,
            "concurrency": concurrency,
            "mode": experiment.mode,
        }
    )
    running: dict[str, set[asyncio.subprocess.Process]] = {}
    stopped: set[str] = set()
    results: list[dict[str, object]] = []
    stopping = asyncio.Event()

    def signal_run(run: str, signal_number: int) -> None:
        for process in running[run]:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal_number)

    def signal_runs(signal_number: int) -> None:
        for run in running:
            signal_run(run, signal_number)

    def interrupt() -> None:
        plan.clear()
        if not stopping.is_set():
            stopping.set()
            report({"event": "stopping"})
            signal_runs(signal.SIGTERM)
        elif any(running.values()):
            report({"event": "killing"})
            signal_runs(signal.SIGKILL)

    def kill(run: str) -> None:
        if not running.get(run):
            return
        if run in stopped:
            report({"event": "killing run", "run": run})
            signal_run(run, signal.SIGKILL)
        else:
            stopped.add(run)
            report({"event": "stopping run", "run": run})
            signal_run(run, signal.SIGTERM)

    held: list[Entry] = []

    def find(entries: list[Entry], run: str) -> Entry | None:
        return next((entry for entry in entries if entry[0] == run), None)

    def arrange(event: str, run: str) -> None:
        pending = [id_ for id_, _ in plan]
        deselected = [id_ for id_, _ in held]
        report({"event": event, "run": run, "pending": pending, "held": deselected})

    def run_next(run: str) -> None:
        entry = find(plan, run)
        if entry is not None:
            plan.remove(entry)
            plan.insert(0, entry)
            arrange("queued", run)

    def toggle(run: str) -> None:
        if stopping.is_set():
            return
        if (entry := find(plan, run)) is not None:
            plan.remove(entry)
            held.append(entry)
            arrange("deselected", run)
        elif (entry := find(held, run)) is not None:
            held.remove(entry)
            plan.append(entry)
            arrange("reselected", run)
            fill()

    ended: dict[str, dict[str, object]] = {}

    def retry(run: str) -> None:
        if stopping.is_set() or run not in ended:
            return
        again = new_run_id(taken)
        planned.add(again)
        plan.append((again, ended[run]))
        report({"event": "retried", "run": run, "retry": again, "params": ended[run]})
        fill()

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
        if not live:
            report({"event": "idle"})
            if finishing:
                done.set()

    def finish() -> None:
        nonlocal finishing
        finishing = True
        if not (live or plan):
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
        result = await execute_run(
            config.root,
            folder,
            experiment.command,
            params,
            running[run],
            stopping,
            invocation,
        )
        del running[run]
        report({"event": "ended", "run": run, **result})
        ended[run] = params
        results.append(result)

    listen(Controls(interrupt, run_next, set_concurrency, toggle, kill, retry, finish))
    fill()
    await done.wait()
    await asyncio.gather(*started)
    return results
