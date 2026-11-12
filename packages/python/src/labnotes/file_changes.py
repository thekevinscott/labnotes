import json
from collections.abc import AsyncIterator

from labnotes.models import LabnotesConfig
from labnotes.tables.open_note_tables import open_note_tables
from labnotes.watch_rows import watch_rows


async def file_changes(config: LabnotesConfig, experiment: str) -> AsyncIterator[str]:
    tables = open_note_tables(config, experiment)
    if tables is None:
        return
    async for row in watch_rows(tables, {"files"}, experiment):
        yield f"data: {json.dumps(row['filename'])}\n\n"
