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
from labnotes.runner.new_run_id import new_run_id
from labnotes.runner.param_grid import param_grid
from labnotes.runner.plan_runs import plan_runs
from labnotes.runner.run_folder import run_folder
from labnotes.tables.list_experiment_runs import list_experiment_runs
from labnotes.tables.open_tables import open_tables


async def run_experiment(
    config: LabnotesConfig,
    name: str,
    experiment: ExperimentConfig,
    concurrency: int,
    report: Report,
    listen: Listen,
) -> list[dict[str, object]]:
    existing = await list_experiment_runs(open_tables(config), name, experiment.counts)
    finished = [json.loads(str(run["params"])) for run in existing if run["counted"]]
    planned: set[str] = set()

    def taken(run: str) -> bool:
        return (
            run in planned or run_folder(config.root, config.runs, name, run).exists()
        )

    plan: list[tuple[str, dict[str, object]]] = []
    for params in plan_runs(
        param_grid(experiment.params), experiment.repeats, finished
    ):
        run = new_run_id(taken)
        planned.add(run)
        plan.append((run, params))
    runs = [{"run": run, "params": params} for run, params in plan]
    report({"event": "planned", "runs": runs, "concurrency": concurrency})
    running: set[asyncio.subprocess.Process] = set()
    results: list[dict[str, object]] = []
    stopping = asyncio.Event()

    def signal_runs(signal_number: int) -> None:
        for process in running:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal_number)

    def interrupt() -> None:
        plan.clear()
        if not stopping.is_set():
            stopping.set()
            report({"event": "stopping"})
            signal_runs(signal.SIGTERM)
        elif running:
            report({"event": "killing"})
            signal_runs(signal.SIGKILL)

    def run_next(run: str) -> None:
        entry = next((entry for entry in plan if entry[0] == run), None)
        if entry is not None:
            plan.remove(entry)
            plan.insert(0, entry)
            pending = [id_ for id_, _ in plan]
            report({"event": "queued", "run": run, "pending": pending})

    async def work() -> None:
        while plan:
            run, params = plan.pop(0)
            folder = run_folder(config.root, config.runs, name, run)
            folder.mkdir(parents=True)
            report({"event": "started", "run": run, "params": params})
            result = await execute_run(
                config.root, folder, experiment.command, params, running, stopping
            )
            report({"event": "ended", "run": run, **result})
            results.append(result)

    listen(Controls(interrupt, run_next))
    await asyncio.gather(*(work() for _ in range(concurrency)))
    return results
