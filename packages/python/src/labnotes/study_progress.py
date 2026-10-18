from typing import cast

from dirsql import DirSQL

from labnotes.cell_progress import cell_progress
from labnotes.count_runs import count_runs
from labnotes.study_runs import study_runs


async def study_progress(
    runs: DirSQL, study: str | None, summary: dict[str, object], columns: list[str]
) -> dict[str, object]:
    varies = cast(dict[str, list[object]], summary["varies"])
    completed_run = str(summary["completed_run"])
    runs_per_cell = summary["runs_per_cell"]
    missing = [key for key in varies if key not in columns]
    progress: dict[str, object] = {
        "runs": 0,
        "completed": 0,
        "filled": None,
        "cells": [],
        "missing_columns": missing,
    }
    if study is None:
        return progress
    source = study_runs(study)
    [totals] = await count_runs(runs, source, completed_run)
    progress.update(totals)
    if missing:
        return progress
    grouped = await count_runs(runs, source, completed_run, group_by=list(varies))
    cells = cell_progress(varies, grouped)
    progress["cells"] = cells
    if isinstance(runs_per_cell, int):
        progress["filled"] = sum(
            min(cast(int, cell["completed"]), runs_per_cell) for cell in cells
        )
    return progress
