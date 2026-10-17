from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

from labnotes.read_config import CONFIG_FILE
from labnotes.models import LabnotesConfig


def context_guide(config: LabnotesConfig | None, cwd: Path) -> str:
    guide = files("labnotes").joinpath("context.md").read_text(encoding="utf-8")
    if config is None:
        project = (
            f"No {CONFIG_FILE} in {cwd}. If this project uses labnotes, run it"
            f" from the folder that holds {CONFIG_FILE}, or pass -c PATH."
        )
    else:
        project = (
            f"Config: {config.path}\n"
            f"Root: {config.root}\n"
            f"Experiments: {config.experiments}\n"
            f"Files: {config.files}\n"
            f"Runs: {config.runs}"
        )
    return f"labnotes {version('labnotes')}\n\n{project}\n\n{guide}"
