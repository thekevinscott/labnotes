from pathlib import Path

from labnotes.copy_experiment import copy_experiment
from labnotes.experiment_definition import experiment_definition
from labnotes.models import LabnotesConfig
from labnotes.runner.new_run_id import new_run_id
from labnotes.runner.runs_parent import runs_parent

STARTER = """\
# Runs from the project root. {run_dir} becomes the run's folder.
command = "uv run script.py --output {run_dir}"
repeats = 1
# true: a failed run starts again in its own folder instead of a new one.
continues = false

# Each combination runs `repeats` times, passed as --name value.
[params]
# model = ["opus", "sonnet"]
"""


def create_experiment(
    config: LabnotesConfig,
    name: str | None,
    source: str | None = None,
    command: str | None = None,
    repeats: int | None = None,
    params: dict[str, list[object]] | None = None,
) -> Path:
    def folder(candidate: str) -> Path:
        return config.root / config.experiments.replace("{experiment}", candidate)

    if config.experiment is not None:
        raise ValueError(
            f"{config.root} is the experiment {config.experiment}; it can't hold others."
        )
    if name is None:
        name = new_run_id(lambda candidate: folder(candidate).exists())
    if name == "new":
        raise ValueError("new is reserved; pick another name.")
    if "/" in name or name.startswith("."):
        raise ValueError(f"{name} can't be an experiment name.")
    path = folder(name)
    if path.exists():
        raise ValueError(f"{name} already exists at {path}.")
    text = STARTER
    if source is not None:
        origin = folder(source) / "experiment.toml"
        if not origin.is_file():
            raise ValueError(f"No experiment.toml for {source} at {origin}.")
        text = origin.read_text(encoding="utf-8")
        copy_experiment(
            origin.parent, path, runs_parent(config.root, config.runs, source)
        )
    else:
        path.mkdir(parents=True)
    (path / "experiment.toml").write_text(
        experiment_definition(text, source, command, repeats, params or {}),
        encoding="utf-8",
    )
    return path
