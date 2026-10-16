def pivot_cells(
    varies: dict[str, list[object]], cells: list[dict[str, object]]
) -> dict[str, object] | None:
    if not varies or not cells:
        return None
    *row_keys, column_key = varies
    width = len(varies[column_key])
    rows = []
    for start in range(0, len(cells), width):
        chunk = cells[start : start + width]
        values = chunk[0]["values"]
        assert isinstance(values, dict)
        rows.append({"labels": [values[key] for key in row_keys], "cells": chunk})
    return {
        "row_keys": row_keys,
        "column_key": column_key,
        "columns": varies[column_key],
        "rows": rows,
    }
