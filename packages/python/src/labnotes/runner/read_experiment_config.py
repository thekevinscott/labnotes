import json
import tomllib
from pathlib import Path

from labnotes.default_counts import DEFAULT_COUNTS
from labnotes.models import ExperimentConfig

SETTINGS = {"name", "command", "repeats", "params", "counts", "mode"}
MODES = ("fill", "adhoc")


def read_experiment_config(path: Path) -> ExperimentConfig:
    try:
        with path.open("rb") as file:
            values = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    unknown = sorted(values.keys() - SETTINGS)
    if unknown:
        raise ValueError(f"{path}: unknown keys {', '.join(unknown)}")
    name = values.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError(f"{path}: name must be a string")
    command = values.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"{path}: command must be a string")
    repeats = values.get("repeats", 1)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError(f"{path}: repeats must be a positive integer")
    params = values.get("params", {})
    if not isinstance(params, dict):
        raise ValueError(f"{path}: params must be a table, like [params]")
    for param, options in params.items():
        if not isinstance(options, list) or not options:
            raise ValueError(f"{path}: params.{param} must be a non-empty list")
    try:
        json.dumps(params)
    except TypeError as error:
        raise ValueError(f"{path}: params can't hold dates or times") from error
    counts = values.get("counts", DEFAULT_COUNTS)
    if not isinstance(counts, str) or not counts.strip():
        raise ValueError(f"{path}: counts must be a SQL condition")
    mode = values.get("mode", "fill")
    if mode not in MODES:
        raise ValueError(f"{path}: mode must be fill or adhoc")
    return ExperimentConfig(command, repeats, params, name, counts, mode)
