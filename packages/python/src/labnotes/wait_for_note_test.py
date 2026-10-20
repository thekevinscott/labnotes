import asyncio
from pathlib import Path
from unittest import mock

from labnotes.wait_for_note import wait_for_note


def test_returns_once_the_tables_list_the_note() -> None:
    with (
        mock.patch(
            "labnotes.wait_for_note.experiment_notes",
            side_effect=[[], [], [{"name": "Untitled.md"}]],
        ) as notes,
        mock.patch("labnotes.wait_for_note.asyncio.sleep") as sleep,
    ):
        asyncio.run(wait_for_note("tables", Path("/p"), "alpha", "Untitled.md"))  # type: ignore[arg-type]

    notes.assert_called_with("tables", Path("/p"), "alpha", "Untitled.md")
    assert notes.call_count == 3
    assert sleep.call_args_list == [mock.call(0.05)] * 2


def test_gives_up_after_two_seconds() -> None:
    with (
        mock.patch("labnotes.wait_for_note.experiment_notes", return_value=[]) as notes,
        mock.patch("labnotes.wait_for_note.asyncio.sleep") as sleep,
    ):
        asyncio.run(wait_for_note("tables", Path("/p"), "alpha", "Untitled.md"))  # type: ignore[arg-type]

    assert notes.call_count == 40
    assert sleep.call_count == 40


def test_waits_for_the_tables_to_hold_the_saved_text() -> None:
    with (
        mock.patch(
            "labnotes.wait_for_note.experiment_notes",
            side_effect=[
                [{"content": "abc"}],
                [{"content": "old"}],
                [{"content": "".join(["n", "ew"])}, {"content": "other"}],
            ],
        ) as notes,
        mock.patch("labnotes.wait_for_note.asyncio.sleep") as sleep,
    ):
        asyncio.run(wait_for_note("tables", Path("/p"), "alpha", "a.md", "new"))  # type: ignore[arg-type]

    assert notes.call_count == 3
    assert sleep.call_count == 2
