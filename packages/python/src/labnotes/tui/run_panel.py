from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from labnotes.tui.log_blocks import LogBlocks
from labnotes.tui.run_output import RunOutput


class RunPanel(Vertical):
    DEFAULT_CSS = "RunPanel #run-id { padding: 0 1; text-style: bold; }"

    def __init__(self, run_id: str, folder: Path) -> None:
        super().__init__()
        self.run_id = run_id
        self.folder = folder

    def compose(self) -> ComposeResult:
        yield Static(self.run_id, id="run-id", markup=False)
        yield LogBlocks(id="blocks")
        yield RunOutput(id="output")

    def on_mount(self) -> None:
        self.follow()
        self.set_interval(0.25, self.follow)

    def follow(self) -> None:
        self.query_one(LogBlocks).follow(self.folder)
        self.query_one(RunOutput).follow(self.folder)
