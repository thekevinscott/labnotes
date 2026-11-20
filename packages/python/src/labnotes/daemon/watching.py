from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
from dirsql import DirSQL


@asynccontextmanager
async def watching(tables: DirSQL) -> AsyncIterator[Any]:
    """A watch stream closed on exit, once dirsql gives streams an aclose()."""
    changes = tables.watch()
    try:
        yield changes
    finally:
        close = getattr(changes, "aclose", None)
        if close is not None:
            # Starlette cancels the scope on hang-up; an unshielded await would never run.
            with anyio.CancelScope(shield=True):
                await close()
