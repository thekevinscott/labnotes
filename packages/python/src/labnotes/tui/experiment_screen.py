from collections.abc import Callable, Mapping
from typing import Any, cast

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
from labnotes.tui.runs_view import Request
from labnotes.tui.stopped_title import stopped_title
from labnotes.tui.view_pane import ViewPane
from labnotes.view.experiment import Experiment
from labnotes.watch_rows import watch_rows

WATCHED = {"runs", "experiment_configs"}
BUILT_IN = "labnotes.tui.runs_browser:RunsBrowser"
MAX_VIEWS = 8


class ExperimentScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("0", "show_view(1)", show=False),
    ]

    def __init__(
        self,
        tables: DirSQL,
        config: LabnotesConfig,
        name: str,
        views: Callable[[str], Request],
    ) -> None:
        super().__init__()
        self.tables = tables
        self.config = config
        self.experiment_name = name
        self.views = views
        self.experiment: dict[str, Any] = {}
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
        if event.state == WorkerState.ERROR:
            self.app.exit(event.worker.error)

    def stopped(self, error: BaseException | None) -> None:
        self.sub_title = stopped_title(self.sub_title, error)

    async def load(self) -> None:
        loaded = await load_experiment(
            self.tables,
            self.config.root,
            self.experiment_name,
            QueryParams(),
        )
        if loaded is None and not self.experiment:
            raise ValueError(f"No experiment named {self.experiment_name}.")
        if loaded is None:
            self.sub_title = f"{self.experiment_name} was removed."
            self.shown = None
            self.deliver(None)
            return
        if not self.experiment:
            await self.add_views(cast(Mapping[str, str], loaded["views"]))
        self.experiment = loaded
        self.sub_title = str(loaded["display_name"])
        self.shown = Experiment(
            self.config.root, self.experiment_name, native_rows(loaded)
        )
        self.deliver(self.shown)

    async def add_views(self, specs: Mapping[str, str]) -> None:
        names = list(specs)[:MAX_VIEWS]
        if names:
            panes = [
                ViewPane(name, specs[name], self.config.root, id=f"view-{number}")
                for number, name in enumerate(names, 2)
            ]
            for pane in panes:
                pane.display = False
            await self.query_one(ContentSwitcher).mount_all(panes)
        # Screen bindings are fixed per class; each screen's view names differ.
        for number, name in enumerate(["runs", *names], 1):
            self._bindings.bind(str(number), f"show_view({number})", name)
        self.refresh_bindings()

    def deliver(
        self, experiment: Experiment | None, paths: frozenset[str] = frozenset()
    ) -> None:
        for pane in self.query(ViewPane):
            pane.deliver(experiment, paths)

    async def watch_files(self) -> None:
        async for row in watch_rows(self.tables, {"run_files"}, self.experiment_name):
            if self.shown is not None:
                self.deliver(self.shown, frozenset({str(row["path"])}))

    def action_show_view(self, number: int) -> None:
        switcher = self.query_one(ContentSwitcher)
        if switcher.current is not None and self.focused is not None:
            self.left[switcher.current] = self.focused
        switcher.current = f"view-{number}"
        self.call_after_refresh(self.refocus, switcher.current)

    def refocus(self, current: str) -> None:
        widget = self.left.get(current)
        if widget is not None and widget.focusable:
            widget.focus()
            return
        self.set_focus(None)
        self.focus_next()

    def action_back(self) -> None:
        if self.query_one(ContentSwitcher).current == "view-1":
            self.app.pop_screen()
        else:
            self.action_show_view(1)
