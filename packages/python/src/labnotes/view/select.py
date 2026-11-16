from textual.message import Message


class Select(Message, namespace="labnotes"):
    """Ask the run TUI to select `run`, a run id, or no run for None."""

    def __init__(self, run: str | None) -> None:
        super().__init__()
        self.run = run
