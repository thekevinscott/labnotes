from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header

from labnotes.tui.log_blocks import LogBlocks
from labnotes.tui.run_output import RunOutput


class RunScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, run_id: str, folder: Path) -> None:
        super().__init__()
        self.run_id = run_id
        self.folder = folder

    def compose(self) -> ComposeResult:
        yield Header()
        yield LogBlocks(id="blocks")
        yield RunOutput(id="output")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.run_id
        self.follow()
        self.set_interval(0.25, self.follow)

    def follow(self) -> None:
        self.query_one(LogBlocks).follow(self.folder)
        self.query_one(RunOutput).follow(self.folder)
