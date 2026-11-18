from textual.message import Message


class Restart(Message, namespace="labnotes"):
    """Ask the run TUI to restart the failed `run`, as `r` does on its row."""

    def __init__(self, run: str) -> None:
        super().__init__()
        self.run = run
