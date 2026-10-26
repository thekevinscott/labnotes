from typing import TypedDict
from urllib.parse import urlencode

from labnotes.format_value import format_value


class Cell(TypedDict):
    values: dict[str, object]
    runs: object
    completed: object
    href: str


def grid_cell(values: dict[str, object], counts: dict[str, object]) -> Cell:
    filters = [(f"f.{key}", format_value(value)) for key, value in values.items()]
    return {
        "values": values,
        "runs": counts.get("runs", 0),
        "completed": counts.get("completed", 0),
        "href": f"?{urlencode(filters)}#runs",
    }
