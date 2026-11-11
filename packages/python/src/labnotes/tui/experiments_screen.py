from dirsql import DirSQL
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header
from textual.worker import Worker, WorkerState

from labnotes.daemon.marker import daemon_marker
from labnotes.models import LabnotesConfig
from labnotes.tables.summarize_experiments import summarize_experiments
from labnotes.tui.experiment_screen import ExperimentScreen
from labnotes.tui.fill_table import fill_table
from labnotes.tui.runs_table import RunsTable


class ExperimentsScreen(Screen[None]):
    def __init__(self, tables: DirSQL, config: LabnotesConfig) -> None:
        super().__init__()
        self.tables = tables
        self.config = config

    def compose(self) -> ComposeResult:
        yield Header()
        yield RunsTable(id="experiments", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_experiments()
        self.set_interval(5, self.refresh_experiments)

    def refresh_experiments(self) -> None:
        """Each query reads the disk afresh, so polling needs no watch on the repo."""
        self.run_worker(self.load(), exit_on_error=False)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        match event.state:
            case WorkerState.ERROR:
                self.app.exit(event.worker.error)

    async def load(self) -> None:
        rows = await summarize_experiments(self.tables)
        rows = [
            {**row, **await daemon_marker(self.tables, self.config, str(row["name"]))}
            for row in rows
        ]
        self.sub_title = "" if rows else "No experiments."
        fill_table(
            self.query_one(DataTable),
            list(next(iter(rows), ())),
            [
                (
                    str(row["name"]),
                    ["" if value is None else str(value) for value in row.values()],
                )
                for row in rows
            ],
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.app.push_screen(
            ExperimentScreen(self.tables, self.config, str(event.row_key.value))
        )
