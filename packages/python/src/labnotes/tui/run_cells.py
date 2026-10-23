from collections.abc import Mapping, Sequence

from labnotes.tui.format_cell import format_cell


def run_cells(
    row: Mapping[str, object],
    columns: Sequence[Mapping[str, str]],
    nested: bool,
    live: bool,
) -> list[object]:
    cells: list[object] = []
    for column in columns:
        key = column["key"]
        if key not in row:
            cells.append("")
        elif key == "id" and nested:
            child = str(row[key]).partition("/")[2]
            cells.append(f"  {child}" if child else str(row[key]))
        else:
            cells.append(format_cell(key, row[key], live))
    return cells
