import tomllib
from pathlib import Path

from labnotes.models import LabnotesConfig
from labnotes.modes import DEFAULT_MODE, MODES
from labnotes.read_path import DEFAULT_PATHS, read_path

CONFIG_FILE = ".labnotes.toml"


def read_config(path: Path) -> LabnotesConfig:
    try:
        with path.open("rb") as file:
            values = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    unknown = sorted(values.keys() - DEFAULT_PATHS.keys())
    if unknown:
        raise ValueError(f"{path}: unknown tables {', '.join(unknown)}")
    paths = {
        table: read_path(path, table, values.get(table, {})) for table in DEFAULT_PATHS
    }
    mode = values.get("experiments", {}).get("mode", DEFAULT_MODE)
    if mode not in MODES:
        raise ValueError(f"{path}: [experiments] mode must be fill or adhoc")
    path = path.resolve()
    return LabnotesConfig(path, path.parent, **paths, mode=mode)
