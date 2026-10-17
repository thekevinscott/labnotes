import json
import tomllib
from pathlib import Path

from labnotes.tables.path_pattern import path_pattern


def read_experiment(root: Path, template: str, path: str) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(f"{template}/experiment.toml").fullmatch(relative)
    if found is None:
        return []
    with Path(path).open("rb") as file:
        config = tomllib.load(file)
    return [{"experiment": found["experiment"], "config": json.dumps(config)}]
