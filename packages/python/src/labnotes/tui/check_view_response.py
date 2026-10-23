import json
from collections.abc import Mapping
from typing import Any

from labnotes.tui.view_column import view_column

SHAPE = "the response must be an object with columns and rows"


def check_view_response(
    reply: str, request: Mapping[str, Any]
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    try:
        response = json.loads(reply)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from error
    if not isinstance(response, dict) or response.keys() != {"columns", "rows"}:
        raise ValueError(SHAPE)
    if not isinstance(response["columns"], list):
        raise ValueError("columns must be a list")
    columns = [view_column(entry) for entry in response["columns"]]
    keys = set()
    for each in columns:
        if each["key"] in keys:
            raise ValueError(f"column {each['key']} is listed twice")
        keys.add(each["key"])
    rows = response["rows"]
    if not isinstance(rows, dict):
        raise ValueError("rows must be an object")
    asked = request["rows"]
    for folder in asked:
        if folder not in rows:
            raise ValueError(f"no row for {folder}")
    for folder, row in rows.items():
        if folder not in asked:
            raise ValueError(f"a row for {folder}, which wasn't asked for")
        if not isinstance(row, dict):
            raise ValueError(f"{folder}: the row must be an object")
        # Native values may ride along unshown, so {**row, ...} needs no filtering.
        stray = sorted(row.keys() - keys - asked[folder].keys())
        if stray:
            raise ValueError(f"{folder}: unknown columns {', '.join(stray)}")
    return columns, rows
