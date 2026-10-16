from math import prod


def summarize_design(design: dict[str, object]) -> dict[str, object]:
    fixed = design.get("fixed")
    varies = design.get("varies")
    fixed = fixed if isinstance(fixed, dict) else {}
    varies = {
        key: values if isinstance(values, list) else [values]
        for key, values in (varies if isinstance(varies, dict) else {}).items()
    }
    runs_per_cell = design.get("runs_per_cell")
    cells = prod(len(values) for values in varies.values())
    known = {"study", "fixed", "varies", "runs_per_cell", "completed_run"}
    return {
        "fixed": fixed,
        "varies": varies,
        "cell_count": cells,
        "runs_per_cell": runs_per_cell,
        "target": cells * runs_per_cell if isinstance(runs_per_cell, int) else None,
        "completed_run": str(design.get("completed_run") or "1"),
        "other": {key: value for key, value in design.items() if key not in known},
    }
