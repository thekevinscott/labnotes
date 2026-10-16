from pathlib import Path

from labnotes.read_note import read_note


def test_reads_experiment_name_and_content(tmp_path: Path) -> None:
    note = tmp_path / "models-effort" / "PLAN.md"
    note.parent.mkdir()
    note.write_text("# Plan\n", encoding="utf-8")

    assert read_note(str(note)) == [
        {"experiment": "models-effort", "name": "PLAN.md", "content": "# Plan\n"}
    ]
