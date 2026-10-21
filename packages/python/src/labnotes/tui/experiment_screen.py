from typing import Any

from dirsql import DirSQL
from starlette.datastructures import QueryParams
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from labnotes.load_experiment import load_experiment
from labnotes.models import LabnotesConfig
from labnotes.tui.invocation_columns import invocation_columns
from labnotes.tui.invocation_rows import invocation_rows
from labnotes.tui.runs_table import RunsTable


class ExperimentScreen(Screen[None]):
    BINDINGS = [
        Binding("space", "toggle", "Open invocation"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, tables: DirSQL, config: LabnotesConfig, name: str) -> None:
        super().__init__()
        self.tables = tables
        self.config = config
        self.experiment_name = name
        self.experiment: dict[str, Any] = {}
        self.opened: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        yield RunsTable(id="runs", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.experiment_name
        self.run_worker(self.load(), exit_on_error=False)

    async def load(self) -> None:
        loaded = await load_experiment(
            self.tables,
            self.config.root,
            self.config.mode,
            self.experiment_name,
            QueryParams(),
        )
        if loaded is None:
            raise ValueError(f"No experiment named {self.experiment_name}.")
        self.experiment = loaded
        self.sub_title = str(loaded["display_name"])
        self.query_one(DataTable).add_columns(*invocation_columns(loaded))
        self.redraw()

    def redraw(self) -> None:
        table = self.query_one(DataTable)
        row = table.cursor_row
        table.clear()
        for key, cells in invocation_rows(self.experiment, self.opened):
            table.add_row(*cells, key=key)
        table.move_cursor(row=row)

    def action_toggle(self) -> None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return
        key = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        groups = {
            group["name"]
            for group in self.experiment["run_groups"] or ()
            if not group["flat"]
        }
        if key in groups:
            self.opened ^= {key}
            self.redraw()
