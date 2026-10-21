from collections.abc import Collection, Mapping
from typing import Any

from labnotes.tui.group_cells import group_cells
from labnotes.tui.run_cells import run_cells


def invocation_rows(
    experiment: Mapping[str, Any], opened: Collection[str]
) -> list[tuple[str, list[object]]]:
    columns = experiment["run_columns"]
    live = experiment["runs_live"]
    groups = experiment["run_groups"]
    if groups is None:
        return [
            (str(run["id"]), run_cells(run, columns, False, live))
            for run in experiment["runs_list"]
        ]
    rows = []
    for group in groups:
        if group["flat"]:
            [run, *_] = group["runs"]
            rows.append((str(run["id"]), run_cells(run, columns, True, live)))
            continue
        is_open = group["name"] in opened
        rows.append((group["name"], group_cells(group, columns, live, is_open)))
        if is_open:
            rows += [
                (str(run["id"]), run_cells(run, columns, True, live))
                for run in group["runs"]
            ]
    return rows
