import json
import tomllib
from pathlib import Path
from typing import Any

from labnotes.compose_experiment import compose_experiment
from labnotes.default_counts import DEFAULT_COUNTS
from labnotes.models import ExperimentConfig
from labnotes.is_non_negative_int import is_non_negative_int
from labnotes.is_non_negative_number import is_non_negative_number
from labnotes.memory_interval import DEFAULT_MEMORY_INTERVAL
from labnotes.is_positive_int import is_positive_int
from labnotes.modes import MODES

SETTINGS = {
    "name",
    "command",
    "repeats",
    "params",
    "counts",
    "mode",
    "concurrency",
    "retries",
    "meta",
    "memory_interval",
    "views",
    "setup",
    "teardown",
    "env",
}
HOOKS = ("setup", "teardown")
VIEWS = {"runs"}


def read_experiment_config(
    path: Path,
    source: str,
    mode: str,
    concurrency: int,
    retries: int,
    defaults: dict[str, object] | None = None,
) -> ExperimentConfig:
    try:
        layer = tomllib.loads(source)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    values: dict[str, Any] = compose_experiment(defaults or {}, layer)
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
    if not is_positive_int(repeats):
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
    mode = values.get("mode", mode)
    if mode not in MODES:
        raise ValueError(f"{path}: mode must be matrix or adhoc")
    concurrency = values.get("concurrency", concurrency)
    if not is_positive_int(concurrency):
        raise ValueError(f"{path}: concurrency must be a positive integer")
    retries = values.get("retries", retries)
    if not is_non_negative_int(retries):
        raise ValueError(f"{path}: retries must be 0 or more")
    meta = values.get("meta")
    if meta is not None and (not isinstance(meta, str) or not meta.strip()):
        raise ValueError(f"{path}: meta must be a string")
    memory_interval = values.get("memory_interval", DEFAULT_MEMORY_INTERVAL)
    if not is_non_negative_number(memory_interval):
        raise ValueError(f"{path}: memory_interval must be 0 or more seconds")
    for hook in HOOKS:
        run = values.get(hook)
        if run is not None and (not isinstance(run, str) or not run.strip()):
            raise ValueError(f"{path}: {hook} must be a string")
    env = values.get("env", {})
    if not isinstance(env, dict):
        raise ValueError(f"{path}: env must be a table, like [env]")
    for key, value in env.items():
        if key.startswith("LABNOTES_"):
            raise ValueError(f"{path}: env.{key} is reserved for labnotes")
        if not isinstance(value, str):
            raise ValueError(f"{path}: env.{key} must be a string")
    views = values.get("views", {})
    if not isinstance(views, dict):
        raise ValueError(f"{path}: views must be a table, like [views]")
    unknown = sorted(views.keys() - VIEWS)
    if unknown:
        raise ValueError(f"{path}: unknown keys in views: {', '.join(unknown)}")
    runs = views.get("runs")
    if runs is not None and (not isinstance(runs, str) or not runs.strip()):
        raise ValueError(f"{path}: views.runs must be a command")
    return ExperimentConfig(
        command,
        repeats,
        params,
        name,
        counts,
        mode,
        concurrency,
        retries,
        meta,
        memory_interval,
        values.get("setup"),
        values.get("teardown"),
        env,
    )
