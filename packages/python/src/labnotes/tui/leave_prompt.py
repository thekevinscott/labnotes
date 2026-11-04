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
        Binding("enter,ctrl+c,s", "dismiss('stop')", "Stop runs"),
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, count: int) -> None:
        super().__init__()
        self.count = count

    def compose(self) -> ComposeResult:
        runs = "run" if self.count == 1 else "runs"
        yield Static(
            f"{self.count} {runs} still going. "
            "Stop them (enter or s) / cancel (esc).",
            id="prompt",
        )


class DetachedLeavePrompt(LeavePrompt):
    """Choose explicitly whether a detached daemon should keep its cells."""

    BINDINGS = [
        Binding("s", "dismiss('stop')", "Stop runs"),
        Binding("enter,l", "dismiss('leave')", "Leave running"),
        Binding("escape", "dismiss", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        runs = "run" if self.count == 1 else "runs"
        yield Static(
            f"{self.count} {runs} still going. "
            "Stop them (s) / leave running (enter or l) / cancel (esc).",
            id="prompt",
        )
