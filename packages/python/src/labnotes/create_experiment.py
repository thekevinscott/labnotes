from pathlib import Path

from labnotes.models import LabnotesConfig
from labnotes.runner.new_run_id import new_run_id

STARTER = """\
# Runs from the project root. {run_dir} becomes the run's folder.
command = "uv run script.py --output {run_dir}"
repeats = 1

# Each combination runs `repeats` times, passed as --name value.
[params]
# model = ["opus", "sonnet"]
"""


def create_experiment(config: LabnotesConfig, name: str | None) -> Path:
    def folder(candidate: str) -> Path:
        return config.root / config.experiments.replace("{experiment}", candidate)

    if name is None:
        name = new_run_id(lambda candidate: folder(candidate).exists())
    if name == "new":
        raise ValueError("new is reserved; pick another name.")
    if "/" in name or name.startswith("."):
        raise ValueError(f"{name} can't be an experiment name.")
    path = folder(name)
    if path.exists():
        raise ValueError(f"{name} already exists at {path}.")
    path.mkdir(parents=True)
    (path / "experiment.toml").write_text(STARTER, encoding="utf-8")
    return path
