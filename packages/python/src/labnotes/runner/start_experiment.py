import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path

from labnotes.models import LabnotesConfig, Start
from labnotes.runner.hold_folder import hold_folder
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.run_experiment import run_experiment


def start_experiment(
    config: LabnotesConfig,
    name: str,
    experiment_config: Path | None,
    concurrency: int | None,
    drive: Callable[[Start, str], list[dict[str, object]]],
) -> list[dict[str, object]]:
    experiment, concurrency, runs = asyncio.run(
        prepare_experiment(config, name, experiment_config, concurrency)
    )
    try:
        with hold_folder(runs):
            start = partial(run_experiment, config, name, experiment, concurrency)
            return drive(start, experiment.name or name)
    except BlockingIOError as error:
        raise ValueError(f"{name} is already running ({runs} is held).") from error
