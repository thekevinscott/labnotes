import json
from collections.abc import AsyncIterator

from dirsql import DirSQL

from labnotes.watch_rows import watch_rows


async def file_changes(tables: DirSQL, experiment: str) -> AsyncIterator[str]:
    async for row in watch_rows(tables, {"files"}, experiment):
        yield f"data: {json.dumps(row['filename'])}\n\n"
