from collections.abc import Mapping

from labnotes.runner.fill_dirs import fill_dirs
from labnotes.runner.placeholders import HOOK_PLACEHOLDERS, PLACEHOLDERS


def fill_experiment_env(
    configured: Mapping[str, str],
    inherited: Mapping[str, str],
    dirs: Mapping[str, str],
    *,
    hook: str | None = None,
    runs: int = 1,
) -> dict[str, str]:
    caller = {
        key: value
        for key, value in inherited.items()
        if not key.startswith("LABNOTES_")
    }
    filled: dict[str, str] = {}
    for key, value in configured.items():
        if key in caller:
            continue
        used = [name for name in PLACEHOLDERS if f"{{{name}}}" in value]
        if hook is not None and any(name not in HOOK_PLACEHOLDERS for name in used):
            continue
        for name in used:
            if name not in dirs:
                raise ValueError(
                    f"{hook} env.{key} uses {{{name}}}, but this invocation plans "
                    f"{runs} runs. {{{name}}} needs exactly one run in this mode."
                )
        filled[key] = fill_dirs(value, dirs, quote=False)
    return {**filled, **caller}
