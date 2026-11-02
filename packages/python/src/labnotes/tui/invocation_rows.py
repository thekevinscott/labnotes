from collections.abc import Collection, Mapping, Sequence

from labnotes.param_names import param_names
from labnotes.tui.group_cells import group_cells
from labnotes.tui.group_summary import group_summary
from labnotes.tui.run_cells import run_cells
from labnotes.view.experiment import Experiment


def invocation_rows(
    experiment: Experiment,
    opened: Collection[str],
    columns: Sequence[Mapping[str, str]],
    rows: Mapping[str, Mapping[str, object]],
) -> list[tuple[str, list[object]]]:
    live = experiment.live
    runs = experiment.runs

    def shown_run(folder: str, nested: bool) -> tuple[str, list[object]]:
        cells = run_cells(rows[folder], columns, nested, live)
        return str(runs[folder]["id"]), cells

    if experiment.groups is None:
        return [shown_run(folder, False) for folder in runs]
    params = param_names(experiment.config)
    shown = []
    for group in experiment.groups:
        if group.flat:
            shown.append(shown_run(group.folders[0], True))
            continue
        is_open = group.name in opened
        members = [runs[folder] for folder in group.folders]
        summary = group_summary(group, members, params)
        shown.append((group.name, group_cells(summary, columns, live, is_open)))
        if is_open:
            shown += [shown_run(folder, True) for folder in group.folders]
    return shown
