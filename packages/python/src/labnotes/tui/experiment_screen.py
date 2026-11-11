from types import MappingProxyType
from typing import Any

from dirsql import DirSQL
from starlette.datastructures import QueryParams
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Footer, Header
from textual.worker import Worker, WorkerState

from labnotes.load_experiment import load_experiment
from labnotes.models import LabnotesConfig
from labnotes.tui.native_rows import native_rows
from labnotes.tui.reload_on_change import reload_on_change
from labnotes.tui.stopped_title import stopped_title
from labnotes.tui.view_pane import ViewPane
from labnotes.tui.view_switcher import ViewSwitcher
from labnotes.view.experiment import Experiment
from labnotes.watch_rows import watch_rows

WATCHED = {"runs", "experiment_configs"}
BUILT_IN = "labnotes.tui.runs_browser:RunsBrowser"


class ExperimentScreen(ViewSwitcher, Screen[None]):
    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(
        self,
        tables: DirSQL,
        config: LabnotesConfig,
        name: str,
    ) -> None:
        super().__init__()
        self.tables = tables
        self.config = config
        self.experiment_name = name
        self.found = False
        self.shown: Experiment | None = None
        self.left: dict[str, Widget] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with ContentSwitcher(initial="view-1"):
            yield ViewPane("runs", BUILT_IN, self.config.root, id="view-1")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.experiment_name
        self.run_worker(
            reload_on_change(
                watch_rows(self.tables, WATCHED, self.experiment_name),
                self.load,
                self.stopped,
            ),
            exit_on_error=False,
        )
        self.run_worker(self.watch_files(), exit_on_error=False)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        match event.state:
            case WorkerState.ERROR:
                self.app.exit(event.worker.error)

    def stopped(self, error: BaseException | None) -> None:
        self.sub_title = stopped_title(self.sub_title, error)

    async def load(self) -> None:
        loaded: dict[str, Any] | None = await load_experiment(
            self.tables,
            self.config.root,
            self.experiment_name,
            QueryParams(),
        )
        if loaded is None and not self.found:
            raise ValueError(f"No experiment named {self.experiment_name}.")
        if loaded is None:
            self.sub_title = f"{self.experiment_name} was removed."
            self.shown = None
            self.deliver(None)
            return
        if not self.found:
            await self.add_views(loaded["views"], self.config.root)
        self.found = True
        self.sub_title = str(loaded["display_name"])
        self.shown = Experiment(
            self.config.root,
            self.experiment_name,
            native_rows(loaded),
            MappingProxyType(loaded["config"] or {}),
        )
        self.deliver(self.shown)

    async def watch_files(self) -> None:
        async for row in watch_rows(self.tables, {"run_files"}, self.experiment_name):
            if self.shown is not None:
                self.deliver(self.shown, frozenset({str(row["path"])}))

    def action_back(self) -> None:
        match self.query_one(ContentSwitcher).current:
            case "view-1":
                self.app.pop_screen()
            case _:
                self.action_show_view(1)
