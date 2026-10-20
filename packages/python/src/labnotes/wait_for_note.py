import asyncio
from pathlib import Path

from dirsql import DirSQL

from labnotes.experiment_notes import experiment_notes


async def wait_for_note(tables: DirSQL, root: Path, experiment: str, note: str) -> None:
    for _ in range(40):
        if await experiment_notes(tables, root, experiment, note):
            return
        await asyncio.sleep(0.05)
