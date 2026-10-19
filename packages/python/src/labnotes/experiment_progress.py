from typing import cast

from dirsql import DirSQL

from labnotes.cell_progress import cell_progress
from labnotes.count_runs import count_runs


async def experiment_progress(
    tables: DirSQL, source: str, summary: dict[str, object]
) -> dict[str, object]:
    varies = cast(dict[str, list[object]], summary["varies"])
    completed_run = str(summary["completed_run"])
    runs_per_cell = summary["runs_per_cell"]
    [totals] = await count_runs(tables, source, completed_run)
    progress: dict[str, object] = {**totals, "filled": None, "cells": []}
    if runs_per_cell is None:
        return progress
    grouped = await count_runs(tables, source, completed_run, group_by=list(varies))
    cells = cell_progress(varies, grouped)
    progress["cells"] = cells
    if summary["target"] is None:
        return progress
    progress["filled"] = sum(
        min(cast(int, cell["completed"]), cast(int, runs_per_cell)) for cell in cells
    )
    return progress
