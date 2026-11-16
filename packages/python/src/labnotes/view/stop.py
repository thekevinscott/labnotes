from textual.message import Message


class Stop(Message, namespace="labnotes"):
    """Ask the run TUI to stop `run`, as `x` does on its row."""

    def __init__(self, run: str) -> None:
        super().__init__()
        self.run = run
