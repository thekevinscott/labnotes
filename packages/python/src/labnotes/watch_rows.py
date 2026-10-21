from collections.abc import AsyncIterator, Collection
from typing import Any

from dirsql import DirSQL


async def watch_rows(
    tables: DirSQL, names: Collection[str], experiment: str | None = None
) -> AsyncIterator[dict[str, Any]]:
    async for event in tables.watch():
        row = event.row or event.old_row
        if event.table in names and row and experiment in (None, row["experiment"]):
            yield row
