from pathlib import Path

from labnotes.models import LabnotesConfig


def hook_folder(config: LabnotesConfig, experiment: str, hook: str, stamp: str) -> Path:
    folder = config.root / config.experiments.replace("{experiment}", experiment)
    return folder / ".labnotes" / "logs" / hook / stamp
