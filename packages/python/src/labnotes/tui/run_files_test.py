from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.run_files import FILES, RunFiles

MODULE = "labnotes.tui.run_files"


class Table:
    """A DataTable stand-in that keeps rows in order, keyed by file."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.rows: dict[mock.Mock, list[object]] = {}
        self.columns: list[str] = []
        self.cursor_row = 0
        self.cleared = 0
        self.focus = mock.Mock()

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def cursor_coordinate(self) -> int:
        return self.cursor_row

    def coordinate_to_cell_key(self, row: int) -> Any:
        return mock.Mock(row_key=list(self.rows)[row])

    def add_column(self, label: str, key: str) -> None:
        self.columns.append(key)

    def add_row(self, *cells: object, key: str) -> None:
        self.rows[mock.Mock(value=key)] = list(cells)

    def update_cell(
        self, row: str, column: str, value: object, **kwargs: object
    ) -> None:
        [found] = [key for key in self.rows if key.value == row]
        self.rows[found][self.columns.index(column)] = value

    def clear(self) -> None:
        self.rows.clear()
        self.cleared += 1

    def move_cursor(self, row: int) -> None:
        self.cursor_row = row

    def shown(self) -> list[tuple[object, ...]]:
        return [(key.value, *cells) for key, cells in self.rows.items()]


@pytest.fixture(autouse=True)
def widgets() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(f"{MODULE}.DataTable", side_effect=Table) as table,
        mock.patch(f"{MODULE}.FileTail") as tail,
    ):
        yield {"table": table, "tail": tail}


def rows(*found: tuple[str, int]) -> list[dict[str, object]]:
    return [{"path": path, "size": size} for path, size in found]


def test_holds_a_file_list_beside_a_tail(widgets: dict[str, mock.MagicMock]) -> None:
    files = RunFiles(id="files")
    assert (files.id, files.folder, files.count) == ("files", None, 0)
    assert list(files.compose()) == [files.table, files.tail]
    assert files.table.kwargs == {"id": "file-list", "cursor_type": "row"}  # type: ignore[attr-defined]
    widgets["tail"].assert_called_once_with(id="file-tail")


def test_names_its_columns_on_mount() -> None:
    files = RunFiles()
    files.on_mount()
    assert files.table.columns == ["file", "size"]  # type: ignore[attr-defined]


def test_lists_files_by_path_with_their_size() -> None:
    files = RunFiles()
    files.on_mount()
    files.show_files(rows(("a.log", 12), ("ckpt/e1.pt", 2_000_000)))
    assert files.table.shown() == [  # type: ignore[attr-defined]
        ("a.log", "a.log", "12 bytes"),
        ("ckpt/e1.pt", "ckpt/e1.pt", "2.0 MB"),
    ]
    assert files.count == 2


def test_updates_sizes_in_place_when_the_same_files_grow() -> None:
    files = RunFiles()
    files.on_mount()
    files.show_files(rows(("a.log", 12)))
    files.show_files(rows(("a.log", 3000)))
    table = files.table
    assert table.shown() == [("a.log", "a.log", "3.0 kB")]  # type: ignore[attr-defined]
    assert table.cleared == 1  # type: ignore[attr-defined]


def test_keeps_the_cursor_on_its_file_when_files_arrive() -> None:
    files = RunFiles()
    files.on_mount()
    files.show_files(rows(("b.log", 1), ("c.log", 1)))
    files.table.move_cursor(row=1)
    files.show_files(rows(("a.log", 1), ("b.log", 1), ("c.log", 1)))
    assert files.table.cursor_row == 2
    assert files.count == 3


def test_leaves_the_cursor_alone_when_its_file_is_gone() -> None:
    files = RunFiles()
    files.on_mount()
    files.show_files(rows(("b.log", 1), ("c.log", 1)))
    files.table.move_cursor(row=1)
    files.show_files(rows(("a.log", 1)))
    assert files.table.shown() == [("a.log", "a.log", "1 byte")]  # type: ignore[attr-defined]


def test_follow_watches_a_new_folder_once_and_follows_the_tail(
    tmp_path: Path,
) -> None:
    files = RunFiles()
    with (
        mock.patch.object(files, "run_worker") as run_worker,
        mock.patch.object(files, "watch", return_value="watching") as watch,
    ):
        files.follow(tmp_path)
        files.follow(tmp_path)
    watch.assert_called_once_with(tmp_path)
    run_worker.assert_called_once_with(
        "watching", group="files", exclusive=True, exit_on_error=False
    )
    assert files.folder == tmp_path
    assert files.tail.follow.call_count == 2  # type: ignore[attr-defined]


def test_reset_forgets_the_folder_and_its_files(tmp_path: Path) -> None:
    files = RunFiles()
    files.on_mount()
    files.show_files(rows(("a.log", 1)))
    files.folder = tmp_path
    workers = mock.Mock()
    with mock.patch.object(
        RunFiles, "workers", new_callable=mock.PropertyMock, return_value=workers
    ):
        files.reset()
    workers.cancel_group.assert_called_once_with(files, "files")
    assert (files.folder, files.count, files.table.shown()) == (None, 0, [])  # type: ignore[attr-defined]
    files.tail.reset.assert_called_once_with()  # type: ignore[attr-defined]


async def test_watch_lists_the_folder_then_relists_on_each_file_change(
    tmp_path: Path,
) -> None:
    files = RunFiles()
    files.on_mount()
    answers = [rows(("a.log", 1)), rows(("a.log", 1), ("b.log", 2))]
    tables = mock.Mock()
    tables.query = mock.AsyncMock(side_effect=answers)

    async def changes() -> AsyncIterator[Any]:
        yield mock.Mock(table="other")
        yield mock.Mock(table="files")

    tables.watch.return_value = changes()
    with mock.patch(f"{MODULE}.open_folder_files", return_value=tables) as opened:
        await files.watch(tmp_path)
    opened.assert_called_once_with(tmp_path)
    assert tables.query.await_args_list == [mock.call(FILES), mock.call(FILES)]
    assert [row[0] for row in files.table.shown()] == ["a.log", "b.log"]  # type: ignore[attr-defined]


def test_picking_a_file_tails_it(tmp_path: Path) -> None:
    files = RunFiles()
    files.folder = tmp_path
    event = mock.Mock(row_key=mock.Mock(value="ckpt/e1.log"))
    files.on_data_table_row_selected(event)
    event.stop.assert_called_once_with()
    files.tail.open.assert_called_once_with(tmp_path / "ckpt/e1.log")  # type: ignore[attr-defined]


def test_picking_before_a_folder_is_known_does_nothing() -> None:
    files = RunFiles()
    event = mock.Mock()
    files.on_data_table_row_selected(event)
    event.stop.assert_called_once_with()
    files.tail.open.assert_not_called()  # type: ignore[attr-defined]


def test_focus_goes_to_the_file_list() -> None:
    files = RunFiles()
    assert files.focus(scroll_visible=False) is files
    files.table.focus.assert_called_once_with(False)  # type: ignore[attr-defined]


def test_lists_files_in_path_order() -> None:
    assert "FROM files" in FILES
    assert FILES.rstrip().endswith("ORDER BY path")
