from typing import Any

from dirsql import DirSQL
from starlette.datastructures import QueryParams
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header
from textual.worker import Worker, WorkerState

from labnotes.load_experiment import load_experiment
from labnotes.models import LabnotesConfig
from labnotes.tui.fill_table import fill_table
from labnotes.tui.invocation_columns import invocation_columns
from labnotes.tui.invocation_rows import invocation_rows
from labnotes.tui.reload_on_change import reload_on_change
from labnotes.tui.run_screen import RunScreen
from labnotes.tui.runs_table import RunsTable
from labnotes.watch_rows import watch_rows

WATCHED = {"runs", "experiment_configs"}


class ExperimentScreen(Screen[None]):
    BINDINGS = [
        Binding("enter", "open_row", "Open", priority=True),
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
        self.run_worker(
            reload_on_change(
                watch_rows(self.tables, WATCHED, self.experiment_name), self.load
            ),
            exit_on_error=False,
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self.app.exit(event.worker.error)

    async def load(self) -> None:
        loaded = await load_experiment(
            self.tables,
            self.config.root,
            self.config.mode,
            self.experiment_name,
            QueryParams(),
        )
        if loaded is None and not self.experiment:
            raise ValueError(f"No experiment named {self.experiment_name}.")
        if loaded is None:
            self.sub_title = f"{self.experiment_name} was removed."
            fill_table(self.query_one(DataTable), [], [])
            return
        self.experiment = loaded
        self.sub_title = str(loaded["display_name"])
        self.redraw()

    def redraw(self) -> None:
        fill_table(
            self.query_one(DataTable),
            invocation_columns(self.experiment),
            invocation_rows(self.experiment, self.opened),
        )

    def action_open_row(self) -> None:
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
            return
        runs = {str(run["id"]): run for run in self.experiment["runs_list"]}
        folder = self.config.root / str(runs[key]["folder"])
        self.app.push_screen(RunScreen(key, folder))
