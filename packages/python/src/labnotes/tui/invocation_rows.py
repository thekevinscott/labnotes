from collections.abc import Collection, Mapping, Sequence
from typing import Any

from labnotes.tui.group_cells import group_cells
from labnotes.tui.run_cells import run_cells


def invocation_rows(
    experiment: Mapping[str, Any],
    opened: Collection[str],
    columns: Sequence[Mapping[str, str]],
    rows: Mapping[str, Mapping[str, object]],
) -> list[tuple[str, list[object]]]:
    live = experiment["runs_live"]
    groups = experiment["run_groups"]

    def cells(run: Mapping[str, object], nested: bool) -> list[object]:
        return run_cells(rows[str(run["folder"])], columns, nested, live)

    if groups is None:
        return [(str(run["id"]), cells(run, False)) for run in experiment["runs_list"]]
    shown = []
    for group in groups:
        if group["flat"]:
            [run, *_] = group["runs"]
            shown.append((str(run["id"]), cells(run, True)))
            continue
        is_open = group["name"] in opened
        shown.append((group["name"], group_cells(group, columns, live, is_open)))
        if is_open:
            shown += [(str(run["id"]), cells(run, True)) for run in group["runs"]]
    return shown
