from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Static

from labnotes.tui.fill_table import fill_table
from labnotes.tui.invocation_columns import invocation_columns
from labnotes.tui.invocation_rows import invocation_rows
from labnotes.tui.native_rows import native_rows
from labnotes.tui.run_output import RunOutput
from labnotes.tui.run_panel import RunPanel
from labnotes.tui.runs_table import RunsTable
from labnotes.tui.runs_view import Request, RunsView
from labnotes.view.changed import Changed


class Host(Protocol):
    experiment: dict[str, Any]
    views: Callable[[str], Request]


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
        self.view: RunsView | None = None
        self.experiment: dict[str, Any] = {}
        self.opened: set[str] = set()
        self.viewing: str | None = None
        self.root = Path()

    @property
    def host(self) -> Host:
        # The built-in view reads labnotes' own data from the screen that mounts it.
        return cast(Host, self.screen)

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
        if message.experiment is None:
            fill_table(self.query_one(DataTable), [], [])
            return
        loaded = self.host.experiment
        self.experiment = loaded
        self.root = message.experiment.root
        command = loaded["runs_view"]
        if command is not None and self.view is None:
            self.view = RunsView(self.host.views(str(command)))
        if self.view is not None:
            self.view.update(invocation_columns(loaded), native_rows(loaded))
            self.ask(self.view)
        self.redraw()

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
        if self.view is None:
            columns = invocation_columns(self.experiment)
            rows = native_rows(self.experiment)
        else:
            columns, rows = self.view.table()
        fill_table(
            self.query_one(DataTable),
            [column["label"] for column in columns],
            invocation_rows(self.experiment, self.opened, columns, rows),
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
        panel = RunPanel(key, self.root / str(runs[key]["folder"]))
        self.viewing = key
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
