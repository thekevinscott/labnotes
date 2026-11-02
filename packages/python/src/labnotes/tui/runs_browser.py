from collections.abc import Mapping
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Static

from labnotes.runs_view_command import runs_view_command
from labnotes.tui.fill_table import fill_table
from labnotes.tui.run_output import RunOutput
from labnotes.tui.run_panel import RunPanel
from labnotes.tui.runs_table import RunsTable
from labnotes.tui.runs_view import RunsView
from labnotes.tui.table_columns import table_columns
from labnotes.tui.table_rows import table_rows
from labnotes.tui.view_process import ViewProcess
from labnotes.view.changed import Changed
from labnotes.view.experiment import Experiment


class RunsBrowser(Widget):
    """Show an experiment's runs, then a run's output: the built-in view."""

    DEFAULT_CSS = """
    RunsBrowser RunsTable { height: 1fr; }
    RunsBrowser #view-status { color: $text-warning; }
    """
    BINDINGS = [
        Binding("enter", "open_row", "Open", priority=True),
        Binding("escape", "close_run", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.process: ViewProcess | None = None
        self.view: RunsView | None = None
        self.experiment = Experiment(Path(), "", ())
        self.viewing: str | None = None

    def compose(self) -> ComposeResult:
        yield RunsTable(id="runs", cursor_type="row")
        yield Static(id="view-status")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if action == "open_row":
            return self.viewing is None
        if action == "close_run":
            return self.viewing is not None
        return True

    def on_labnotes_changed(self, message: Changed) -> None:
        if message.paths:
            if self.view is not None:
                for path in sorted(message.paths):
                    self.view.touch(path)
                self.ask(self.view)
            return
        experiment = message.experiment
        if experiment is None:
            fill_table(self.query_one(DataTable), [], [])
            return
        self.experiment = experiment
        command = runs_view_command(dict(experiment.config))
        if command is not None and self.view is None:
            self.process = ViewProcess(command, experiment.root)
            self.view = RunsView(self.process.request)
        if self.view is not None:
            rows = {str(row["folder"]): dict(row) for row in experiment.runs}
            self.view.update(table_columns(experiment.config), rows)
            self.ask(self.view)
        self.redraw()

    async def on_unmount(self) -> None:
        if self.process is not None:
            await self.process.close()

    def ask(self, view: RunsView) -> None:
        request = view.next_request()
        if request is not None:
            self.run_worker(self.answer(view, request), exit_on_error=False)

    async def answer(self, view: RunsView, request: dict[str, Any]) -> None:
        if await view.exchange(request):
            self.redraw()
        else:
            self.show_status()
        self.ask(view)

    def redraw(self) -> None:
        rows: Mapping[str, Mapping[str, Any]]
        if self.view is None:
            columns = table_columns(self.experiment.config)
            rows = {str(row["folder"]): row for row in self.experiment.runs}
        else:
            columns, rows = self.view.table()
        fill_table(
            self.query_one(DataTable),
            [column["label"] for column in columns],
            table_rows(self.experiment.runs, columns, rows),
        )
        self.show_status()

    def show_status(self) -> None:
        text = "" if self.view is None else self.view.status()
        status = self.query_one("#view-status", Static)
        status.update(text)
        status.display = bool(text) and self.viewing is None

    async def action_open_row(self) -> None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return
        folder = str(
            table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        )
        ids = {str(row["folder"]): str(row["id"]) for row in self.experiment.runs}
        panel = RunPanel(ids[folder], self.experiment.root / folder)
        self.viewing = folder
        table.display = False
        self.show_status()
        await self.mount(panel)
        panel.query_one(RunOutput).focus()

    def action_close_run(self) -> None:
        self.viewing = None
        self.query_one(RunPanel).remove()
        table = self.query_one(DataTable)
        table.display = True
        table.focus()
        self.show_status()
