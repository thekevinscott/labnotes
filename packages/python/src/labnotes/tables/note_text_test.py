from pathlib import Path

from labnotes.tables.note_text import note_text


def test_reads_markdown(tmp_path: Path) -> None:
    (tmp_path / "plan.md").write_text("plan ✓", encoding="utf-8")

    assert note_text(tmp_path / "plan.md") == "plan ✓"


def test_skips_other_files(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("a,b", encoding="utf-8")

    assert note_text(tmp_path / "data.csv") is None


def test_skips_markdown_that_is_not_utf8(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe")

    assert note_text(tmp_path / "bad.md") is None
