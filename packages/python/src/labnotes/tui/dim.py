from rich.text import Text


def dim(cell: str) -> Text:
    return Text(cell, style="dim")
