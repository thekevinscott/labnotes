import tomllib
from pathlib import Path

from labnotes.models import LabnotesConfig

CONFIG_FILE = ".labnotes.toml"
DEFAULTS = {"experiments": "experiments", "data": "data"}


def find_config(start: Path) -> LabnotesConfig | None:
    for folder in [start, *start.parents]:
        path = folder / CONFIG_FILE
        if path.is_file():
            break
    else:
        return None
    with path.open("rb") as file:
        values = tomllib.load(file)
    unknown = sorted(values.keys() - DEFAULTS.keys())
    if unknown:
        raise ValueError(f"{path}: unknown keys {', '.join(unknown)}")
    folders = {}
    for key, default in DEFAULTS.items():
        value = values.get(key, default)
        if not isinstance(value, str):
            raise ValueError(f"{path}: {key} must be a string")
        folders[key] = folder / Path(value).expanduser()
    return LabnotesConfig(path, folders["experiments"], folders["data"])
