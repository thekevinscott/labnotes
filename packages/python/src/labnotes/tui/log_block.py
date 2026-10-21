from rich.text import Text
from textual.events import Click
from textual.widgets import Static


class LogBlock(Static):
    DEFAULT_CSS = """
    LogBlock { height: auto; }
    LogBlock.-collapsed { height: 1; text-wrap: nowrap; text-overflow: ellipsis; }
    """

    def __init__(self, body: str) -> None:
        super().__init__(classes="-collapsed")
        self.body = body
        self.expanded = False
        self.show()

    def extend(self, text: str) -> None:
        self.body += text
        self.show()

    def on_click(self, _: Click) -> None:
        self.expanded = not self.expanded
        self.set_class(not self.expanded, "-collapsed")
        self.show()

    def show(self) -> None:
        if self.expanded:
            self.update(Text(f"▾ {self.body}"))
        else:
            self.update(Text(f"▸ {self.body}".replace("\n", " ")))
