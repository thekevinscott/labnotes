from math import prod

from labnotes.default_counts import DEFAULT_COUNTS


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
    counts = config.get("counts")
    mode = "adhoc" if config.get("mode") == "adhoc" else "fill"
    return {
        "fixed": {},
        "varies": varies,
        "cell_count": cells,
        "runs_per_cell": repeats,
        "target": cells * repeats if repeats is not None and mode == "fill" else None,
        "completed_run": counts if isinstance(counts, str) else DEFAULT_COUNTS,
        "mode": mode,
        "other": {} if command is None else {"command": command},
    }
