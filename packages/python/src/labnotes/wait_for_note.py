import asyncio
from pathlib import Path

from dirsql import DirSQL

from labnotes.experiment_notes import experiment_notes


async def wait_for_note(
    tables: DirSQL,
    root: Path,
    experiment: str,
    note: str,
    content: str | None = None,
) -> None:
    for _ in range(40):
        found = await experiment_notes(tables, root, experiment, note)
        if found and (content is None or found[0]["content"] == content):
            return
        await asyncio.sleep(0.05)
