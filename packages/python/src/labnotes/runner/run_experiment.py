import asyncio
import contextlib
import json
import os
import signal
from collections.abc import Callable

from labnotes.models import ExperimentConfig, LabnotesConfig
from labnotes.runner.execute_run import execute_run
from labnotes.runner.new_run_id import new_run_id
from labnotes.runner.param_args import param_args
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
    report: Callable[[str], None],
) -> list[dict[str, object]]:
    runs = await list_experiment_runs(open_tables(config), name)
    finished = [json.loads(str(run["params"])) for run in runs if run["exit_code"] == 0]
    plan = plan_runs(param_grid(experiment.params), experiment.repeats, finished)
    report(f"{len(plan)} runs to go, {concurrency} at a time.")
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
        if stopping:
            signal_runs(signal.SIGKILL)
            os._exit(130)
        else:
            stopping = True
            report("Stopping runs. Ctrl-C again to kill them.")
            signal_runs(signal.SIGTERM)

    async def work() -> None:
        while plan:
            params = plan.pop(0)
            run = new_run_id(
                lambda id_: run_folder(config.root, config.runs, name, id_).exists()
            )
            folder = run_folder(config.root, config.runs, name, run)
            folder.mkdir(parents=True)
            report(f"{run} started {' '.join(param_args(params))}".rstrip())
            result = await execute_run(
                config.root, folder, experiment.command, params, running
            )
            outcome = result["error"] or f"exited {result['exit_code']}"
            report(f"{run} {outcome}")
            results.append(result)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, interrupt)
    try:
        await asyncio.gather(*(work() for _ in range(concurrency)))
    finally:
        loop.remove_signal_handler(signal.SIGINT)
    return results
