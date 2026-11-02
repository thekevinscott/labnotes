import shutil
from pathlib import Path


def copy_experiment(source: Path, target: Path, runs: Path) -> None:
    def skip(folder: str, names: list[str]) -> set[str]:
        here = Path(folder)
        if here == runs:
            return {name for name in names if (here / name / "run.json").exists()}
        return {name for name in names if here / name == runs}

    shutil.copytree(source, target, ignore=skip, symlinks=True)
