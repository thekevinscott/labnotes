from datetime import datetime
from pathlib import Path

import pytest

from labnotes.save_conflict_copy import save_conflict_copy

NOW = datetime(2026, 10, 20, 9, 5)


def test_writes_a_dated_sibling_and_leaves_the_note(tmp_path: Path) -> None:
    note = tmp_path / "plan.md"
    note.write_text("mine", encoding="utf-8")

    copy = save_conflict_copy(note, "theirs ✓", NOW)

    assert copy == tmp_path / "plan (Conflicted copy 202610200905).md"
    assert copy.read_text(encoding="utf-8") == "theirs ✓"
    assert note.read_text(encoding="utf-8") == "mine"


@pytest.mark.parametrize("taken", [1, 2])
def test_numbers_past_copies_from_the_same_minute(tmp_path: Path, taken: int) -> None:
    names = [
        "plan (Conflicted copy 202610200905).md",
        "plan (Conflicted copy 202610200905 2).md",
        "plan (Conflicted copy 202610200905 3).md",
    ]
    for name in names[:taken]:
        (tmp_path / name).write_text("earlier", encoding="utf-8")

    copy = save_conflict_copy(tmp_path / "plan.md", "theirs", NOW)

    assert copy == tmp_path / names[taken]
    assert copy.read_text(encoding="utf-8") == "theirs"
    assert (tmp_path / names[0]).read_text(encoding="utf-8") == "earlier"
