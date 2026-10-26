from itertools import product
from typing import TypedDict
from urllib.parse import urlencode

from labnotes.format_value import format_value


class Cell(TypedDict):
    values: dict[str, object]
    runs: object
    completed: object
    href: str


class Row(TypedDict):
    labels: list[object]
    cells: list[Cell]


class Grid(TypedDict):
    row_keys: list[str]
    column_key: str | None
    columns: list[object]
    rows: list[Row]


def _key(value: object) -> object:
    return int(value) if isinstance(value, bool) else value


def _cell(values: dict[str, object], counts: dict[str, object]) -> Cell:
    filters = [(f"f.{key}", format_value(value)) for key, value in values.items()]
    return {
        "values": values,
        "runs": counts.get("runs", 0),
        "completed": counts.get("completed", 0),
        "href": f"?{urlencode(filters)}#runs",
    }


def pivot_runs(axes: dict[str, list[object]], counts: list[dict[str, object]]) -> Grid:
    by_cell = {tuple(_key(row[key]) for key in axes): row for row in counts}
    row_keys = [*axes]
    column_key = row_keys.pop() if row_keys else None
    columns: list[object] = [None] if column_key is None else axes[column_key]
    rows: list[Row] = []
    for labels in product(*(axes[key] for key in row_keys)):
        cells = []
        for column in columns:
            values: dict[str, object] = dict(zip(row_keys, labels))
            if column_key is not None:
                values[column_key] = column
            found = by_cell.get(tuple(_key(values[key]) for key in axes), {})
            cells.append(_cell(values, found))
        rows.append({"labels": list(labels), "cells": cells})
    return {
        "row_keys": row_keys,
        "column_key": column_key,
        "columns": columns,
        "rows": rows,
    }
