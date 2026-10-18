from math import prod

# What the runner counts toward repeats.
COMPLETED_RUN = "exit_code = 0 AND NOT coalesce(excluded, 0)"


def summarize_config(config: dict[str, object] | None) -> dict[str, object]:
    config = config or {}
    params = config.get("params")
    varies = {
        key: values if isinstance(values, list) else [values]
        for key, values in (params if isinstance(params, dict) else {}).items()
    }
    repeats = config.get("repeats", 1) if config else None
    repeats = repeats if isinstance(repeats, int) else None
    cells = prod(len(values) for values in varies.values())
    command = config.get("command")
    return {
        "fixed": {},
        "varies": varies,
        "cell_count": cells,
        "runs_per_cell": repeats,
        "target": cells * repeats if repeats is not None else None,
        "completed_run": COMPLETED_RUN,
        "other": {} if command is None else {"command": command},
    }
