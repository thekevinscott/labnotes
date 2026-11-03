from collections.abc import Mapping, Sequence

from labnotes.tui.run_cells import run_cells


def table_rows(
    runs: Sequence[Mapping[str, object]],
    columns: Sequence[Mapping[str, str]],
    rows: Mapping[str, Mapping[str, object]],
) -> list[tuple[str, list[object]]]:
    folders = [str(run["folder"]) for run in runs]
    return [(folder, run_cells(rows[folder], columns)) for folder in folders]
