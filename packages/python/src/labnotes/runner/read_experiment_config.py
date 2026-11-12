import json
import re
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
from labnotes.config_migration import MISSING_CONTINUES, REMOVED_MODE
from labnotes.is_exit_codes import is_exit_codes
from labnotes.retries import RETRY_EXIT_CODES, RETRY_SECONDS

SHELL_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
SETTINGS = {
    "name",
    "command",
    "repeats",
    "params",
    "counts",
    "concurrency",
    "retries",
    "retry_wait",
    "retry_exit_codes",
    "meta",
    "memory_interval",
    "views",
    "setup",
    "teardown",
    "env",
    "continues",
    "from",
}
HOOKS = ("setup", "teardown")
MAX_VIEWS = 8


def read_experiment_config(
    path: Path,
    source: str,
    concurrency: int,
    retries: int,
    defaults: dict[str, object] | None = None,
    retry_wait: float = RETRY_SECONDS,
    retry_exit_codes: tuple[int, ...] = RETRY_EXIT_CODES,
) -> ExperimentConfig:
    try:
        layer = tomllib.loads(source)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    values: dict[str, Any] = compose_experiment(defaults or {}, layer)
    if "mode" in values:
        raise ValueError(f"{path}: {REMOVED_MODE}")
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
    concurrency = values.get("concurrency", concurrency)
    if not is_positive_int(concurrency):
        raise ValueError(f"{path}: concurrency must be a positive integer")
    retries = values.get("retries", retries)
    if not is_non_negative_int(retries):
        raise ValueError(f"{path}: retries must be 0 or more")
    retry_wait = values.get("retry_wait", retry_wait)
    if not is_non_negative_number(retry_wait):
        raise ValueError(f"{path}: retry_wait must be 0 or more seconds")
    retry_exit_codes = values.get("retry_exit_codes", list(retry_exit_codes))
    if not is_exit_codes(retry_exit_codes):
        raise ValueError(f"{path}: retry_exit_codes must be a list of exit codes 1-255")
    meta = values.get("meta")
    if meta is not None and (not isinstance(meta, str) or not meta.strip()):
        raise ValueError(f"{path}: meta must be a string")
    memory_interval = values.get("memory_interval", DEFAULT_MEMORY_INTERVAL)
    if not is_non_negative_number(memory_interval):
        raise ValueError(f"{path}: memory_interval must be 0 or more seconds")
    origin = values.get("from")
    if origin is not None and (not isinstance(origin, str) or not origin.strip()):
        raise ValueError(f"{path}: from must be an experiment name")
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
        if not SHELL_IDENTIFIER.match(key):
            raise ValueError(
                f"{path}: env.{key} must be a shell identifier"
                " (letters, digits, underscore; not starting with a digit)"
            )
        if not isinstance(value, str):
            raise ValueError(f"{path}: env.{key} must be a string")
    if "continues" not in values:
        raise ValueError(f"{path}: {MISSING_CONTINUES}")
    continues = values["continues"]
    if not isinstance(continues, bool):
        raise ValueError(f"{path}: continues must be true or false")
    views = values.get("views", {})
    if not isinstance(views, dict):
        raise ValueError(f"{path}: views must be a table, like [views]")
    runs = views.get("runs")
    if runs is not None and (not isinstance(runs, str) or not runs.strip()):
        raise ValueError(f"{path}: views.runs must be a command")
    shown = {name: spec for name, spec in views.items() if name != "runs"}
    if len(shown) > MAX_VIEWS:
        raise ValueError(f"{path}: views holds at most {MAX_VIEWS} views besides runs")
    for name, spec in shown.items():
        source, _, cls = spec.rpartition(":") if isinstance(spec, str) else ("", "", "")
        if not source.strip() or not cls.strip():
            raise ValueError(
                f'{path}: views.{name} must be "path/to/file.py:ClassName"'
            )
    return ExperimentConfig(
        command,
        repeats,
        params,
        name,
        counts,
        concurrency,
        retries,
        retry_wait,
        meta,
        memory_interval,
        values.get("setup"),
        values.get("teardown"),
        env,
        continues,
        retry_exit_codes=tuple(retry_exit_codes),
    )
