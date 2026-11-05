import asyncio
import contextlib
import fcntl
import os
from collections.abc import AsyncIterator
from pathlib import Path

from labnotes.runner.run_state import journal_folder


@contextlib.asynccontextmanager
async def planning_lock(root: Path) -> AsyncIterator[None]:
    """Serialize plan reads and claims for every client of one project."""
    folder = journal_folder(root)
    folder.mkdir(parents=True, exist_ok=True)
    lock = os.open(folder / "plan.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                await asyncio.sleep(0.05)
        yield
    finally:
        os.close(lock)
