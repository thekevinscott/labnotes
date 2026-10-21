from dirsql import DirSQL
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header
from textual.worker import Worker, WorkerState

from labnotes.models import LabnotesConfig
from labnotes.tables.summarize_experiments import summarize_experiments
from labnotes.tui.experiment_screen import ExperimentScreen
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
        self.run_worker(self.load(), exit_on_error=False)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self.app.exit(event.worker.error)

    async def load(self) -> None:
        rows = await summarize_experiments(self.tables)
        if not rows:
            self.sub_title = "No experiments."
            return
        table = self.query_one(DataTable)
        table.add_columns(*rows[0])
        for row in rows:
            table.add_row(
                *("" if value is None else str(value) for value in row.values()),
                key=str(row["name"]),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.app.push_screen(
            ExperimentScreen(self.tables, self.config, str(event.row_key.value))
        )
