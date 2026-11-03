from collections.abc import Mapping, Sequence

from labnotes.tui.format_cell import format_cell


def run_cells(
    row: Mapping[str, object], columns: Sequence[Mapping[str, str]]
) -> list[object]:
    return [
        format_cell(column["key"], row[column["key"]]) if column["key"] in row else ""
        for column in columns
    ]
