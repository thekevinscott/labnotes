import time
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from labnotes.tui.format_elapsed import format_elapsed
from labnotes.tui.run_output import RunOutput


class HookPanel(Vertical):
    DEFAULT_CSS = """
    HookPanel { height: 1fr; display: none; }
    HookPanel .hook-header { padding: 0 1; }
    HookPanel RunOutput { height: 1fr; }
    """

    def __init__(self, hook: str, id: str | None = None) -> None:
        super().__init__(id=id)
        self.hook = hook
        self.folder: Path | None = None
        self.began: float | None = None
        self.took: float | None = None
        self.error: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(f"{self.hook}: waiting", classes="hook-header", markup=False)
        yield RunOutput(id=f"{self.hook}-output")

    @property
    def running(self) -> bool:
        return self.began is not None and self.took is None

    @property
    def state(self) -> str:
        if self.began is None:
            return "waiting"
        if self.took is None:
            return "running"
        return "failed" if self.error else "passed"

    def start(self, folder: Path, began: float) -> None:
        self.folder = folder
        self.began = began
        self.tick()

    def end(self, error: str | None, ended: float) -> None:
        self.error = error
        if self.began is not None:
            self.took = ended - self.began
        self.follow()
        self.tick()

    def tick(self) -> None:
        header = self.query_one(".hook-header", Static)
        if self.began is None:
            header.update(f"{self.hook}: waiting")
            return
        took = self.took if self.took is not None else time.monotonic() - self.began
        status = {"running": "running", "passed": "✓", "failed": f"✗ {self.error}"}
        style = "red" if self.error else ""
        header.update(
            Text(f"{self.hook}: {status[self.state]}  {format_elapsed(took)}", style)
        )

    def follow(self) -> None:
        if self.folder is not None:
            self.query_one(RunOutput).follow(self.folder)
