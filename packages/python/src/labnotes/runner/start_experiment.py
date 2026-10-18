from collections.abc import Callable
from functools import partial
from pathlib import Path

from filelock import FileLock, Timeout

from labnotes.models import LabnotesConfig, Start
from labnotes.runner.lock_path import lock_path
from labnotes.runner.read_experiment_config import read_experiment_config
from labnotes.runner.run_experiment import run_experiment


def start_experiment(
    config: LabnotesConfig,
    name: str,
    experiment_config: Path | None,
    concurrency: int,
    drive: Callable[[Start], list[dict[str, object]]],
) -> list[dict[str, object]]:
    if experiment_config is None:
        folder = config.experiments.replace("{experiment}", name)
        experiment_config = config.root / folder / "experiment.toml"
    if not experiment_config.is_file():
        raise ValueError(f"No experiment.toml for {name} at {experiment_config}.")
    experiment = read_experiment_config(experiment_config)
    lock = lock_path(config.root, config.runs, name)
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(lock, blocking=False):
            return drive(partial(run_experiment, config, name, experiment, concurrency))
    except Timeout as error:
        raise ValueError(f"{name} is already running ({lock} is held).") from error
