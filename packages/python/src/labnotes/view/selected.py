from textual.message import Message


class Selected(Message, bubble=False, namespace="labnotes"):
    """Tell a view the run TUI's selected run changed. Handle it as `on_labnotes_selected`."""

    def __init__(self, run: str | None) -> None:
        super().__init__()
        self.run = run
