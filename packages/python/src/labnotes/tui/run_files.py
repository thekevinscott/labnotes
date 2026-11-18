from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, Protocol, Self, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable

from labnotes.tui.file_tail import FileTail
from labnotes.utils.format_bytes import format_bytes


class FileSource(Protocol):
    def run_files(self, run: str) -> AsyncIterator[tuple[str, Any]]: ...


class RunFiles(Horizontal):
    """List a run folder's files and tail the one picked."""

    DEFAULT_CSS = """
    RunFiles { height: 1fr; }
    RunFiles #file-list { width: 40%; height: 1fr; }
    RunFiles #file-tail { width: 1fr; height: 1fr; }
    """

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self.run: str | None = None
        self.folder: Path | None = None
        self.count = 0
        self.table: DataTable[Any] = DataTable(id="file-list", cursor_type="row")
        self.tail = FileTail(id="file-tail")

    def compose(self) -> ComposeResult:
        yield self.table
        yield self.tail

    def on_mount(self) -> None:
        self.table.add_column("file", key="file")
        self.table.add_column("size", key="size")

    def follow(self, run: str, folder: Path) -> None:
        self.folder = folder
        if run != self.run:
            self.run = run
            self.run_worker(
                self.list_files(run),
                group="files",
                exclusive=True,
                exit_on_error=False,
            )
        self.tail.follow()

    def reset(self) -> None:
        self.run = None
        self.folder = None
        self.count = 0
        self.workers.cancel_group(self, "files")
        self.table.clear()
        self.tail.reset()

    async def list_files(self, run: str) -> None:
        shown: dict[str, dict[str, Any]] = {}
        async for kind, data in cast(FileSource, self.app).run_files(run):
            match kind:
                case "state":
                    shown = {row["name"]: row for row in data}
                case "file":
                    shown[data["name"]] = data
                case "remove":
                    shown.pop(data["name"], None)
            self.show_files([shown[name] for name in sorted(shown)])

    def show_files(self, rows: Sequence[dict[str, Any]]) -> None:
        table = self.table
        names = [str(row["name"]) for row in rows]
        self.count = len(names)
        if names == [key.value for key in table.rows]:
            for row in rows:
                table.update_cell(
                    str(row["name"]),
                    "size",
                    format_bytes(row["size"]),
                    update_width=True,
                )
            return
        cursor = (
            table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            if table.row_count
            else None
        )
        table.clear()
        for row in rows:
            name = str(row["name"])
            table.add_row(name, format_bytes(row["size"]), key=name)
        if cursor in names:
            table.move_cursor(row=names.index(cursor))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        if self.folder is not None:
            self.tail.open(self.folder / str(event.row_key.value))

    def focus(self, scroll_visible: bool = True) -> Self:
        self.table.focus(scroll_visible)
        return self
