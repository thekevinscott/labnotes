from textual.message import Message


class Selected(Message, namespace="labnotes"):
    """Say which run is selected. Handle it as `on_labnotes_selected`.

    labnotes sends it to every view when the selected run changes. A view
    that posts one selects that run for every view.
    """

    def __init__(self, run: str | None) -> None:
        super().__init__()
        self.run = run
