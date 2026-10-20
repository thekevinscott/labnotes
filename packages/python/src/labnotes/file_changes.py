import json
from collections.abc import AsyncIterator

from dirsql import DirSQL


async def file_changes(tables: DirSQL, experiment: str) -> AsyncIterator[str]:
    async for event in tables.watch():
        row = event.row or event.old_row
        if event.table == "files" and row and row["experiment"] == experiment:
            yield f"data: {json.dumps(row['filename'])}\n\n"
