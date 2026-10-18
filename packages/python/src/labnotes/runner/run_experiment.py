import asyncio
import contextlib
import json
import os
import signal

from labnotes.models import ExperimentConfig, LabnotesConfig, Listen, Report
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
    runs = await list_experiment_runs(open_tables(config), name)
    finished = [json.loads(str(run["params"])) for run in runs if run["exit_code"] == 0]
    plan = plan_runs(param_grid(experiment.params), experiment.repeats, finished)
    report({"event": "planned", "runs": len(plan), "concurrency": concurrency})
    running: set[asyncio.subprocess.Process] = set()
    results: list[dict[str, object]] = []
    stopping = False

    def signal_runs(signal_number: int) -> None:
        for process in running:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal_number)

    def interrupt() -> None:
        nonlocal stopping
        plan.clear()
        if not stopping:
            stopping = True
            report({"event": "stopping"})
            signal_runs(signal.SIGTERM)
        elif running:
            report({"event": "killing"})
            signal_runs(signal.SIGKILL)

    async def work() -> None:
        while plan:
            params = plan.pop(0)
            run = new_run_id(
                lambda id_: run_folder(config.root, config.runs, name, id_).exists()
            )
            folder = run_folder(config.root, config.runs, name, run)
            folder.mkdir(parents=True)
            report({"event": "started", "run": run, "params": params})
            result = await execute_run(
                config.root, folder, experiment.command, params, running
            )
            report({"event": "ended", "run": run, **result})
            results.append(result)

    listen(interrupt)
    await asyncio.gather(*(work() for _ in range(concurrency)))
    return results
