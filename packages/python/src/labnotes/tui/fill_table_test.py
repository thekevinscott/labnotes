from typing import Any
from unittest import mock

from labnotes.tui.fill_table import fill_table


class FakeTable:
    def __init__(self) -> None:
        self.labels: list[str] = []
        self.rows: list[tuple[str, list[object]]] = []
        self.numbers: list[str] = []
        self.cursor_row = 0
        self.cursor_coordinate = "cursor"

    @property
    def columns(self) -> dict[str, mock.Mock]:
        return {label: mock.Mock(label=label) for label in self.labels}

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def coordinate_to_cell_key(self, coordinate: str) -> mock.Mock:
        assert coordinate == "cursor"
        key = mock.Mock()
        key.row_key.value = self.rows[self.cursor_row][0]
        return key

    def clear(self, columns: bool = False) -> None:
        self.rows = []
        self.numbers = []
        self.cursor_row = 0
        if columns:
            self.labels = []

    def add_columns(self, *labels: str) -> None:
        self.labels += labels

    def add_row(self, *cells: object, key: str, label: str) -> None:
        self.rows.append((key, list(cells)))
        self.numbers.append(label)

    def move_cursor(self, *, row: int) -> None:
        self.cursor_row = min(row, max(len(self.rows) - 1, 0))


def fill(table: FakeTable, columns: list[str], *keys: str) -> None:
    rows: Any = [(key, [key, len(key)]) for key in keys]
    fill_table(table, columns, rows)  # type: ignore[arg-type]


def shown(table: FakeTable) -> tuple[list[str], list[str], int]:
    return table.labels, [key for key, _ in table.rows], table.cursor_row


def test_fills_an_empty_table() -> None:
    table = FakeTable()

    fill(table, ["name", "size"], "ab", "c")

    assert shown(table) == (["name", "size"], ["ab", "c"], 0)
    assert table.rows[0] == ("ab", ["ab", 2])


def test_keeps_the_cursor_on_its_row_when_rows_arrive_above() -> None:
    table = FakeTable()
    fill(table, ["name", "size"], "b", "c")
    table.move_cursor(row=1)

    fill(table, ["name", "size"], "a", "b", "c")

    assert shown(table) == (["name", "size"], ["a", "b", "c"], 2)


def test_keeps_the_cursor_row_when_its_row_goes() -> None:
    table = FakeTable()
    fill(table, ["name", "size"], "a", "b", "c")
    table.move_cursor(row=1)

    fill(table, ["name", "size"], "a", "c")

    assert shown(table) == (["name", "size"], ["a", "c"], 1)


def test_keeps_the_columns_when_they_match() -> None:
    table = FakeTable()
    fill(table, ["name", "size"], "a")
    table.add_columns = mock.Mock()  # type: ignore[method-assign]

    fill(table, ["name", "size"], "b")

    table.add_columns.assert_not_called()
    assert shown(table) == (["name", "size"], ["b"], 0)


def test_replaces_the_columns_when_they_change() -> None:
    table = FakeTable()
    fill(table, ["name", "size"], "a")

    fill(table, ["name", "length"], "a")

    assert shown(table) == (["name", "length"], ["a"], 0)


def test_empties_the_table() -> None:
    table = FakeTable()
    fill(table, ["name", "size"], "a")

    fill(table, [])

    assert shown(table) == ([], [], 0)


def test_numbers_rows_from_one() -> None:
    table = FakeTable()
    fill(table, ["name", "size"], "ab", "c", "d")

    fill(table, ["name", "size"], "c", "d")

    assert table.numbers == ["1", "2"]
