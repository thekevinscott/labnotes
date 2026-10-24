from textual.app import App
from textual.binding import Binding

from labnotes.models import LabnotesConfig
from labnotes.tables.open_tables import open_tables
from labnotes.tui.experiment_screen import ExperimentScreen
from labnotes.tui.experiments_screen import ExperimentsScreen
from labnotes.tui.runs_view import Request
from labnotes.tui.view_process import ViewProcess


class BrowseApp(App[BaseException | None]):
    BINDINGS = [Binding("ctrl+c", "quit", "Quit")]

    def __init__(self, config: LabnotesConfig, name: str | None) -> None:
        super().__init__()
        self.config = config
        self.experiment_name = name
        self.title = config.root.name
        self.views: dict[str, ViewProcess] = {}

    def on_mount(self) -> None:
        tables = open_tables(self.config, run_files=True)
        self.push_screen(ExperimentsScreen(tables, self.config, self.view_request))
        if self.experiment_name is not None:
            self.push_screen(
                ExperimentScreen(
                    tables, self.config, self.experiment_name, self.view_request
                )
            )

    def view_request(self, command: str) -> Request:
        if command not in self.views:
            self.views[command] = ViewProcess(command, self.config.root)
        return self.views[command].request

    async def on_unmount(self) -> None:
        for process in self.views.values():
            await process.close()
