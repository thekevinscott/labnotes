from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static


class LeavePrompt(ModalScreen[str | None]):
    CSS = """
    LeavePrompt { align: center middle; }
    #prompt { width: auto; padding: 1 2; border: round $accent; }
    """
    BINDINGS = [
        Binding("enter,ctrl+c", "dismiss('leave')", "Leave running"),
        Binding("s", "dismiss('stop')", "Stop them"),
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, count: int) -> None:
        super().__init__()
        self.count = count

    def compose(self) -> ComposeResult:
        runs = "run" if self.count == 1 else "runs"
        yield Static(
            f"{self.count} {runs} still going. "
            "Leave them running (enter) / stop them (s) / cancel (esc).",
            id="prompt",
        )
