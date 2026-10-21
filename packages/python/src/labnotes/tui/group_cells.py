from collections.abc import Mapping, Sequence
from typing import Any

from rich.text import Text

from labnotes.format_value import format_value


def group_cells(
    group: Mapping[str, Any], columns: Sequence[str], live: bool
) -> list[object]:
    status = Text.assemble(
        (f"{group['passed']}✓", "green"), " ", (f"{group['failed']}✕", "red")
    )
    if group["unfinished"]:
        mark, style = ("◐", "yellow") if live else ("–", "dim")
        status.append(f" {group['unfinished']}{mark}", style=style)
    cells: list[object] = [status, group["name"], str(len(group["runs"]))]
    for column in columns[1:]:
        if column == "started":
            cells.append(group["started"] or "")
        elif column in group["shared"]:
            cells.append(format_value(group["shared"][column]))
        else:
            cells.append("")
    return cells
