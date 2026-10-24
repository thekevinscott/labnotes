from datetime import UTC, datetime

from rich.text import Text

from labnotes.format_value import format_value
from labnotes.tui.dim import dim
from labnotes.tui.format_elapsed import format_elapsed


def format_cell(key: str, value: object, live: bool) -> object:
    if key == "status" and value == "passed":
        return Text("✓", style="green")
    if key == "status" and value == "failed":
        return Text("✕", style="red")
    if key == "status" and value == "unfinished":
        return Text("◐", style="yellow") if live else dim("–")
    if key == "duration" and isinstance(value, int) and not isinstance(value, bool):
        return format_elapsed(value)
    if key == "started" and isinstance(value, str):
        try:
            started = datetime.fromisoformat(value)
        except ValueError:
            return value
        if started.tzinfo is not None:
            started = started.astimezone(UTC)
        return started.strftime("%Y-%m-%d %H:%M:%S")
    return format_value(value)
