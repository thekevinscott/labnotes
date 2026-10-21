import asyncio
from collections.abc import AsyncIterator
from unittest import mock

from labnotes.file_changes import file_changes


def test_streams_the_experiments_changed_files_as_server_sent_events() -> None:
    async def rows() -> AsyncIterator[dict[str, str]]:
        yield {"experiment": "alpha", "filename": "plan ✓.md"}
        yield {"experiment": "alpha", "filename": "gone.md"}

    tables = mock.Mock()

    async def collect() -> list[str]:
        return [message async for message in file_changes(tables, "alpha")]

    with mock.patch(
        "labnotes.file_changes.watch_rows", return_value=rows()
    ) as watch_rows:
        streamed = asyncio.run(collect())

    watch_rows.assert_called_once_with(tables, {"files"}, "alpha")
    assert streamed == ['data: "plan \\u2713.md"\n\n', 'data: "gone.md"\n\n']
