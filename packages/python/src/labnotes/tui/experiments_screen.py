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
from labnotes.tui.reload_on_change import reload_on_change
from labnotes.tui.runs_table import RunsTable
from labnotes.tui.stopped_title import stopped_title
from labnotes.watch_rows import watch_rows

WATCHED = {"files", "runs", "experiment_configs"}


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
        self.run_worker(
            reload_on_change(watch_rows(self.tables, WATCHED), self.load, self.stopped),
            exit_on_error=False,
        )
        self.set_interval(5, self.refresh_daemons)

    def refresh_daemons(self) -> None:
        """Update socket ownership even when no experiment file changes."""
        self.run_worker(self.load(), exit_on_error=False)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:  # probe
            self.app.exit(event.worker.error)

    def stopped(self, error: BaseException | None) -> None:
        self.sub_title = stopped_title(self.sub_title, error)

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
