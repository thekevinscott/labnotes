import json
from pathlib import Path

from labnotes.read_design import read_design


def test_reads_name_study_and_design(tmp_path: Path) -> None:
    design = tmp_path / "models-effort" / "design.yaml"
    design.parent.mkdir()
    design.write_text("study: v2\nfixed:\n  model: opus\n", encoding="utf-8")

    [row] = read_design(str(design))

    assert row["name"] == "models-effort"
    assert row["study"] == "v2"
    assert json.loads(str(row["design"])) == {"study": "v2", "fixed": {"model": "opus"}}


def test_empty_design_has_no_study(tmp_path: Path) -> None:
    design = tmp_path / "empty" / "design.yaml"
    design.parent.mkdir()
    design.write_text("", encoding="utf-8")

    [row] = read_design(str(design))

    assert row["study"] is None
    assert row["design"] == "{}"
