from collections.abc import Sequence

from textual.widgets import DataTable


def fill_table(
    table: DataTable[object],
    columns: Sequence[str],
    rows: Sequence[tuple[str, Sequence[object]]],
) -> None:
    # The cursor follows its row by key, so rows arriving above it don't move it.
    row = table.cursor_row
    key = (
        table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        if table.row_count
        else None
    )
    if [str(column.label) for column in table.columns.values()] == list(columns):
        table.clear()
    else:
        table.clear(columns=True)
        table.add_columns(*columns)
    keys = [each for each, _ in rows]
    for each, cells in rows:
        table.add_row(*cells, key=each)
    table.move_cursor(row=keys.index(key) if key in keys else row)
