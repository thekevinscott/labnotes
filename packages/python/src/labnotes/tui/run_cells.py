from collections.abc import Mapping, Sequence

from rich.text import Text

from labnotes.format_duration import format_duration
from labnotes.format_value import format_value
from labnotes.tui.dim import dim


def run_cells(
    run: Mapping[str, object], columns: Sequence[str], nested: bool, live: bool
) -> list[object]:
    if run["labnotes_unfinished"]:
        status = Text("◐", style="yellow") if live else dim("–")
    elif run["labnotes_completed"]:
        status = Text("✓", style="green")
    else:
        status = Text("✕", style="red")
    cells: list[object] = [status]
    for column in columns:
        value = run[column]
        if column == "id" and nested:
            child = str(value).partition("/")[2]
            cells += [f"  {child}" if child else str(value), ""]
        elif column == "duration":
            cells.append(format_duration(value))  # type: ignore[arg-type]
        else:
            cells.append(format_value(value))
    return cells
