from collections.abc import Mapping
from typing import Any


def invocation_columns(experiment: Mapping[str, Any]) -> list[dict[str, str]]:
    keys = list(experiment["run_columns"])
    if experiment["run_groups"] is not None:
        keys.insert(1, "runs")
    return [{"key": "status", "label": ""}, *({"key": k, "label": k} for k in keys)]
