from collections.abc import Mapping, Sequence
from typing import Any

from rich.text import Text

from labnotes.format_value import format_value


def group_cells(
    group: Mapping[str, Any],
    columns: Sequence[Mapping[str, str]],
    live: bool,
    opened: bool,
) -> list[object]:
    cells: list[object] = []
    for column in columns:
        key = column["key"]
        if key == "status":
            status = Text.assemble(
                (f"{group['passed']}✓", "green"), " ", (f"{group['failed']}✕", "red")
            )
            if group["unfinished"]:
                mark, style = ("◐", "yellow") if live else ("–", "dim")
                status.append(f" {group['unfinished']}{mark}", style=style)
            cells.append(status)
        elif key == "id":
            cells.append(f"{'▾' if opened else '▸'} {group['name']}")
        elif key == "runs":
            cells.append(str(len(group["runs"])))
        elif key == "started":
            cells.append(group["started"] or "")
        elif key in group["shared"]:
            cells.append(format_value(group["shared"][key]))
        else:
            cells.append("")
    return cells
