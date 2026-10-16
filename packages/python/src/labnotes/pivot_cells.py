from itertools import product


def pivot_cells(
    varies: dict[str, list[object]], cells: list[dict[str, object]]
) -> dict[str, object] | None:
    if not varies or not cells:
        return None
    *row_keys, column_key = varies
    width = len(varies[column_key])
    labels = product(*(varies[key] for key in row_keys))
    rows = [
        {"labels": list(label), "cells": cells[start : start + width]}
        for label, start in zip(labels, range(0, len(cells), width))
    ]
    return {
        "row_keys": row_keys,
        "column_key": column_key,
        "columns": varies[column_key],
        "rows": rows,
    }
