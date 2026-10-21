from collections.abc import Mapping
from typing import Any


def invocation_columns(experiment: Mapping[str, Any]) -> list[str]:
    columns = ["", *experiment["run_columns"]]
    if experiment["run_groups"] is not None:
        columns.insert(2, "runs")
    return columns
