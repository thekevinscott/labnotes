import tomllib
from pathlib import Path

from labnotes.models import LabnotesConfig
from labnotes.is_positive_int import is_positive_int
from labnotes.modes import DEFAULT_MODE, MODES
from labnotes.runner.read_experiment_config import SETTINGS
from labnotes.read_path import DEFAULT_PATHS, read_path

CONFIG_FILE = ".labnotes.toml"


def read_config(path: Path) -> LabnotesConfig:
    try:
        with path.open("rb") as file:
            values = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    unknown = sorted(values.keys() - {*DEFAULT_PATHS, "experiment"})
    if unknown:
        raise ValueError(f"{path}: unknown tables {', '.join(unknown)}")
    experiments = values.get("experiments", {})
    defaults = values.get("experiment", {})
    if not isinstance(defaults, dict):
        raise ValueError(f"{path}: experiment must be a table, like [experiment]")
    unknown = sorted(defaults.keys() - SETTINGS)
    if unknown:
        raise ValueError(f"{path}: unknown keys in [experiment]: {', '.join(unknown)}")
    root = path.resolve().parent
    # An [experiments] path means many experiments, each taking [experiment] as
    # its defaults; without one, [experiment] makes the root the experiment.
    single = (root / "experiment.toml").is_file() or (
        "experiment" in values
        and not (isinstance(experiments, dict) and "path" in experiments)
    )
    paths = {
        table: read_path(path, table, values.get(table, {}), single=single)
        for table in DEFAULT_PATHS
    }
    mode = experiments.get("mode", DEFAULT_MODE)
    if mode not in MODES:
        raise ValueError(f"{path}: [experiments] mode must be matrix or adhoc")
    concurrency = experiments.get("concurrency", 1)
    if not is_positive_int(concurrency):
        raise ValueError(
            f"{path}: [experiments] concurrency must be a positive integer"
        )
    return LabnotesConfig(
        path.resolve(),
        root,
        **paths,
        mode=mode,
        concurrency=concurrency,
        experiment=root.name if single else None,
        defaults=defaults,
    )
