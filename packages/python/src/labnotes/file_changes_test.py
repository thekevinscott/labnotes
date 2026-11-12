import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest import mock

from labnotes.file_changes import file_changes


def collect(config: Any) -> list[str]:
    async def drain() -> list[str]:
        return [message async for message in file_changes(config, "alpha")]

    return asyncio.run(drain())


def test_streams_the_experiments_changed_files_as_server_sent_events() -> None:
    async def rows() -> AsyncIterator[dict[str, str]]:
        yield {"experiment": "alpha", "filename": "plan ✓.md"}
        yield {"experiment": "alpha", "filename": "gone.md"}

    config = mock.Mock()
    with (
        mock.patch("labnotes.file_changes.open_note_tables") as opened,
        mock.patch(
            "labnotes.file_changes.watch_rows", return_value=rows()
        ) as watch_rows,
    ):
        streamed = collect(config)

    opened.assert_called_once_with(config, "alpha")
    watch_rows.assert_called_once_with(opened.return_value, {"files"}, "alpha")
    assert streamed == ['data: "plan \\u2713.md"\n\n', 'data: "gone.md"\n\n']


def test_streams_nothing_without_a_notes_folder() -> None:
    with (
        mock.patch("labnotes.file_changes.open_note_tables", return_value=None),
        mock.patch("labnotes.file_changes.watch_rows") as watch_rows,
    ):
        assert collect(mock.Mock()) == []

    watch_rows.assert_not_called()
