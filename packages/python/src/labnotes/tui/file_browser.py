from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Log, Static

from labnotes.utils.format_bytes import format_bytes
from labnotes.view.changed import Changed
from labnotes.view.daemon import Daemon
from labnotes.view.selected import Selected


class FileBrowser(Horizontal):
    """List the selected run's files and tail the one you choose."""

    MAX_LINES = 10_000
    DEFAULT_CSS = """
    FileBrowser { height: 1fr; }
    FileBrowser #file-list { width: 50; }
    FileBrowser #file-tail { width: 1fr; }
    FileBrowser #files { height: 1fr; }
    FileBrowser #tail { height: 1fr; }
    FileBrowser #files-title, FileBrowser #tail-title { padding: 0 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.daemon: Daemon | None = None
        self.run: str | None = None
        self.listed: str | None = None
        self.runs: frozenset[str] = frozenset()
        self.newline = False

    def compose(self) -> ComposeResult:
        with Vertical(id="file-list"):
            yield Static("Select a run to see its files.", id="files-title")
            yield DataTable(id="files", cursor_type="row")
        with Vertical(id="file-tail"):
            yield Static(id="tail-title")
            yield Log(id="tail", max_lines=self.MAX_LINES)

    def on_mount(self) -> None:
        table = self.query_one("#files", DataTable)
        table.add_column("name", key="name")
        table.add_column("size", key="size")

    def on_labnotes_changed(self, message: Changed) -> None:
        if message.daemon is not None:
            self.daemon = message.daemon
        if message.experiment is not None:
            self.runs = frozenset(str(row["id"]) for row in message.experiment.runs)
        if self.run is not None and self.listed != self.run and self.run in self.runs:
            self.list_run()

    def on_labnotes_selected(self, message: Selected) -> None:
        if message.run != self.run:
            self.run = message.run
            self.list_run()

    def list_run(self) -> None:
        if self.daemon is None:
            return
        self.listed = self.run
        self.workers.cancel_group(self, "files")
        self.workers.cancel_group(self, "tail")
        self.query_one("#files", DataTable).clear()
        self.query_one("#tail", Log).clear()
        self.query_one("#tail-title", Static).update("")
        title = self.query_one("#files-title", Static)
        if self.run is None:
            title.update("Select a run to see its files.")
            return
        title.update(f"Files in {self.run}")
        self.run_worker(
            self.follow_files(self.daemon, self.run),
            group="files",
            exclusive=True,
            exit_on_error=False,
        )

    async def follow_files(self, daemon: Daemon, run: str) -> None:
        table = self.query_one("#files", DataTable)
        try:
            async for kind, data in daemon.follow(f"/runs/{quote(run)}/files"):
                match kind:
                    case "state":
                        table.clear()
                        for row in data:
                            table.add_row(
                                row["name"], format_bytes(row["size"]), key=row["name"]
                            )
                    case "file":
                        self.put(data)
                    case "remove" if data["name"] in table.rows:
                        table.remove_row(data["name"])
        except ValueError:
            self.listed = None
            self.query_one("#files-title", Static).update(f"No files yet in {run}.")

    def put(self, row: Mapping[str, Any]) -> None:
        table = self.query_one("#files", DataTable)
        name, size = str(row["name"]), format_bytes(row["size"])
        if name in table.rows:
            table.update_cell(name, "size", size, update_width=True)
            return
        cursor = (
            table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if table.row_count
            else None
        )
        table.add_row(name, size, key=name)
        table.sort("name")
        if cursor is not None:
            table.move_cursor(row=table.get_row_index(cursor), animate=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        if self.daemon is None or self.run is None:
            return
        name = str(event.row_key.value)
        self.query_one("#tail", Log).clear()
        self.query_one("#tail-title", Static).update(name)
        self.run_worker(
            self.follow_tail(self.daemon, self.run, name),
            group="tail",
            exclusive=True,
            exit_on_error=False,
        )

    async def follow_tail(self, daemon: Daemon, run: str, name: str) -> None:
        log = self.query_one("#tail", Log)
        route = f"/runs/{quote(run)}/files/{quote(name)}"
        try:
            async for kind, data in daemon.follow(route):
                match kind, data:
                    case "state", {"text": str(text)}:
                        log.clear()
                        self.newline = False
                        self.write(log, text)
                    case "state", {"type": kind_of, "size": size}:
                        log.clear()
                        log.write_line(
                            f"Binary file ({kind_of}, {format_bytes(size)}), not shown."
                        )
                    case "append", {"text": str(text)}:
                        self.write(log, text)
        except ValueError:
            log.clear()
            log.write_line(f"{name} is gone.")

    # Log.write leaves an empty last line after a trailing newline; hold it back
    # so the last line shown is the file's last line.
    def write(self, log: Log, text: str) -> None:
        if self.newline:
            text = "\n" + text
        self.newline = text.endswith("\n")
        log.write(text.removesuffix("\n"))
