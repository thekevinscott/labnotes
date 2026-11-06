from collections.abc import AsyncIterator, Collection
from typing import Any

from dirsql import DirSQL

from labnotes.matching_rows import matching_rows


def watch_rows(
    tables: DirSQL, names: Collection[str], experiment: str | None = None
) -> AsyncIterator[dict[str, Any]]:
    # Not a generator: dirsql arms its watcher inside watch(), and callers
    # rely on that happening before their first query.
    return matching_rows(tables.watch(), names, experiment)
