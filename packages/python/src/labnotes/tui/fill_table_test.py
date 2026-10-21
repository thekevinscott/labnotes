import asyncio
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.widgets import DataTable

from labnotes.tui.fill_table import fill_table


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield DataTable()


def on_table[T](steps: Callable[[DataTable[object]], T]) -> T:
    async def drive() -> T:
        app = Host()
        async with app.run_test():
            return steps(app.query_one(DataTable))

    return asyncio.run(drive())


def shown(table: DataTable[object]) -> tuple[list[str], list[list[object]], int]:
    return (
        [str(column.label) for column in table.columns.values()],
        [table.get_row_at(index) for index in range(table.row_count)],
        table.cursor_row,
    )


def rows(*keys: str) -> list[tuple[str, list[object]]]:
    return [(key, [key, len(key)]) for key in keys]


def test_fills_an_empty_table() -> None:
    def steps(table: DataTable[object]) -> object:
        fill_table(table, ["name", "size"], rows("ab", "c"))
        return shown(table)

    assert on_table(steps) == (["name", "size"], [["ab", 2], ["c", 1]], 0)


def test_keeps_the_cursor_on_its_row_when_rows_arrive_above() -> None:
    def steps(table: DataTable[object]) -> object:
        fill_table(table, ["name", "size"], rows("b", "c"))
        table.move_cursor(row=1)
        fill_table(table, ["name", "size"], rows("a", "b", "c"))
        return shown(table)

    assert on_table(steps) == (
        ["name", "size"],
        [["a", 1], ["b", 1], ["c", 1]],
        2,
    )


def test_keeps_the_cursor_row_when_its_row_goes() -> None:
    def steps(table: DataTable[object]) -> object:
        fill_table(table, ["name", "size"], rows("a", "b", "c"))
        table.move_cursor(row=1)
        fill_table(table, ["name", "size"], rows("a", "c"))
        return shown(table)

    assert on_table(steps) == (["name", "size"], [["a", 1], ["c", 1]], 1)


def test_replaces_the_columns_when_they_change() -> None:
    def steps(table: DataTable[object]) -> object:
        fill_table(table, ["name", "size"], rows("a"))
        fill_table(table, ["name", "length"], rows("a"))
        return shown(table)

    assert on_table(steps) == (["name", "length"], [["a", 1]], 0)


def test_empties_the_table() -> None:
    def steps(table: DataTable[object]) -> object:
        fill_table(table, ["name", "size"], rows("a"))
        fill_table(table, [], [])
        return shown(table)

    assert on_table(steps) == ([], [], 0)
