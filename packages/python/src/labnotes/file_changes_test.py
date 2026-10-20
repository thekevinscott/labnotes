import asyncio
from collections.abc import AsyncIterator
from unittest import mock

from labnotes.file_changes import file_changes


def event(table: str | None, row: object = None, old_row: object = None) -> mock.Mock:
    return mock.Mock(table=table, row=row, old_row=old_row)


def test_streams_the_experiments_changed_files_as_server_sent_events() -> None:
    async def events() -> AsyncIterator[mock.Mock]:
        yield event("files", {"experiment": "a", "filename": "plan ✓.md"})
        yield event("files", {"experiment": "b", "filename": "other.md"})
        yield event("runs", {"experiment": "a", "filename": "run.json"})
        yield event(None)
        yield event("files", None, {"experiment": "a", "filename": "gone.md"})

    tables = mock.Mock()
    tables.watch.return_value = events()

    async def collect() -> list[str]:
        return [message async for message in file_changes(tables, "a")]

    assert asyncio.run(collect()) == [
        'data: "plan \\u2713.md"\n\n',
        'data: "gone.md"\n\n',
    ]
