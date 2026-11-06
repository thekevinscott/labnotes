from collections.abc import AsyncIterable, AsyncIterator, Collection
from typing import Any


async def matching_rows(
    events: AsyncIterable[Any], names: Collection[str], experiment: str | None = None
) -> AsyncIterator[dict[str, Any]]:
    async for event in events:
        row = event.row or event.old_row
        if event.table in names and row and experiment in (None, row["experiment"]):
            yield row
