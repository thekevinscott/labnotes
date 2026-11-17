from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio  # noqa: F401
from dirsql import DirSQL


@asynccontextmanager
async def watching(tables: DirSQL) -> AsyncIterator[Any]:
    """A watch stream closed on exit, once dirsql gives streams an aclose()."""
    yield tables.watch()
