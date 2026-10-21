from textual.app import App
from textual.binding import Binding

from labnotes.models import LabnotesConfig
from labnotes.tables.open_tables import open_tables
from labnotes.tui.experiment_screen import ExperimentScreen
from labnotes.tui.experiments_screen import ExperimentsScreen


class BrowseApp(App[BaseException | None]):
    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(self, config: LabnotesConfig, name: str | None) -> None:
        super().__init__()
        self.config = config
        self.experiment_name = name
        self.title = config.root.name

    def on_mount(self) -> None:
        tables = open_tables(self.config)
        self.push_screen(ExperimentsScreen(tables, self.config))
        if self.experiment_name is not None:
            self.push_screen(
                ExperimentScreen(tables, self.config, self.experiment_name)
            )
