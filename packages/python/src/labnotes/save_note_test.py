from pathlib import Path

from labnotes.save_note import save_note


def test_writes_over_the_version_it_was_based_on(tmp_path: Path) -> None:
    note = tmp_path / "plan.md"
    note.write_text("old ✓", encoding="utf-8")

    assert save_note(note, "old ✓", "new ✓") is None
    assert note.read_text(encoding="utf-8") == "new ✓"


def test_refuses_a_stale_write_and_returns_the_file(tmp_path: Path) -> None:
    note = tmp_path / "plan.md"
    note.write_text("theirs ✓", encoding="utf-8")

    assert save_note(note, "old", "mine") == "theirs ✓"
    assert note.read_text(encoding="utf-8") == "theirs ✓"
