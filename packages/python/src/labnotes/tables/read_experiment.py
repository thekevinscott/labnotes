import json
import tomllib
from pathlib import Path

from labnotes.compose_experiment import compose_experiment
from labnotes.tables.experiment_toml import experiment_toml
from labnotes.tables.path_pattern import path_pattern


def read_experiment(
    root: Path,
    template: str,
    path: str,
    experiment: str | None = None,
    defaults: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(experiment_toml(template)).fullmatch(relative)
    if found is None:
        return []
    source = Path(path).read_text(encoding="utf-8")
    config = compose_experiment(defaults or {}, tomllib.loads(source))
    return [
        {
            "experiment": experiment or found["experiment"],
            "config": json.dumps(config),
            "source": source,
        }
    ]
