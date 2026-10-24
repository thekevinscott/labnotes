from typing import Any

from labnotes.view.build import Build


def answer(build: Build, request: dict[str, Any]) -> dict[str, Any]:
    columns, row = build(request["columns"])
    return {
        "columns": columns,
        "rows": {folder: row(native) for folder, native in request["rows"].items()},
    }
