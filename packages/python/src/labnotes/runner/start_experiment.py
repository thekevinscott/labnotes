import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path

from labnotes.models import LabnotesConfig, Start
from labnotes.runner.hold_folder import hold_folder
from labnotes.runner.read_experiment_config import read_experiment_config
from labnotes.runner.run_experiment import run_experiment
from labnotes.runner.runs_parent import runs_parent
from labnotes.tables.file_text import file_text


def start_experiment(
    config: LabnotesConfig,
    name: str,
    experiment_config: Path | None,
    concurrency: int | None,
    drive: Callable[[Start, str], list[dict[str, object]]],
) -> list[dict[str, object]]:
    if experiment_config is None:
        folder = config.experiments.replace("{experiment}", name)
        experiment_config = config.root / folder / "experiment.toml"
    source = asyncio.run(file_text(config.root, experiment_config))
    if source is None:
        raise ValueError(f"No experiment.toml for {name} at {experiment_config}.")
    experiment = read_experiment_config(
        experiment_config, source, config.mode, config.concurrency
    )
    if concurrency is None:
        concurrency = experiment.concurrency
    runs = runs_parent(config.root, config.runs, name)
    runs.mkdir(parents=True, exist_ok=True)
    try:
        with hold_folder(runs):
            start = partial(run_experiment, config, name, experiment, concurrency)
            return drive(start, experiment.name or name)
    except BlockingIOError as error:
        raise ValueError(f"{name} is already running ({runs} is held).") from error
