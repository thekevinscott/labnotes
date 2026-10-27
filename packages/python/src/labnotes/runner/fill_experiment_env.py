from collections.abc import Mapping

from labnotes.runner.fill_ids import fill_ids


def fill_experiment_env(
    configured: Mapping[str, str],
    inherited: Mapping[str, str],
    ids: Mapping[str, str],
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
        for name in ("run_dir", "run_id"):
            if f"{{{name}}}" in value and name not in ids:
                raise ValueError(
                    f"{hook} env.{key} uses {{{name}}}, but this invocation plans "
                    f"{runs} runs. {{{name}}} needs exactly one; "
                    "use {invocation_id} instead."
                )
        filled[key] = fill_ids(value, ids, quote=False)
    return {**filled, **caller}
