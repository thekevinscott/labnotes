from pathlib import Path


def run_folder(root: Path, template: str, experiment: str, run: str) -> Path:
    return root / template.replace("{experiment}", experiment).replace("{run}", run)
