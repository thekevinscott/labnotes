from collections.abc import Mapping

from labnotes.runner.fill_dirs import fill_dirs
from labnotes.runner.placeholders import PLACEHOLDERS


def fill_experiment_env(
    configured: Mapping[str, str],
    inherited: Mapping[str, str],
    dirs: Mapping[str, str],
) -> dict[str, str]:
    caller = {
        key: value
        for key, value in inherited.items()
        if not key.startswith("LABNOTES_")
    }
    filled = {
        key: fill_dirs(value, dirs, quote=False)
        for key, value in configured.items()
        if key not in caller
        and all(name in dirs for name in PLACEHOLDERS if f"{{{name}}}" in value)
    }
    return {**filled, **caller}
