from pathlib import Path

from labnotes.models import ExperimentConfig, LabnotesConfig
from labnotes.runner.read_experiment_config import read_experiment_config
from labnotes.tables.file_text import file_text


async def prepare_experiment(
    config: LabnotesConfig,
    name: str,
    experiment_config: Path | None,
    concurrency: int | None,
) -> tuple[ExperimentConfig, int]:
    if experiment_config is None:
        folder = config.experiments.replace("{experiment}", name)
        experiment_config = config.root / folder / "experiment.toml"
    source = await file_text(config.root, experiment_config)
    if source is None:
        raise ValueError(f"No experiment.toml for {name} at {experiment_config}.")
    experiment = read_experiment_config(
        experiment_config, source, config.mode, config.concurrency
    )
    return experiment, experiment.concurrency if concurrency is None else concurrency
