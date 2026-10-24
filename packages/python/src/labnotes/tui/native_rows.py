import json
from collections.abc import Mapping
from typing import Any

JSON_FIELDS = ("params", "meta", "run")


def native_row(run: Mapping[str, Any]) -> dict[str, Any]:
    row = {key: value for key, value in run.items() if not key.startswith("labnotes_")}
    for key in JSON_FIELDS:
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])
    if run["labnotes_unfinished"]:
        row["status"] = "unfinished"
    elif run["labnotes_completed"]:
        row["status"] = "passed"
    else:
        row["status"] = "failed"
    row["started"] = run["created"]
    return row


def native_rows(experiment: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(run["folder"]): native_row(run) for run in experiment["runs_list"]}
