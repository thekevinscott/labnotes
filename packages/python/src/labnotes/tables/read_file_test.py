import os
from pathlib import Path

import pytest

from labnotes.tables.read_file import read_file


def touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    os.utime(path, ns=(0, 1_792_281_600_123_456_789))
    return str(path)


def test_reads_a_file_row(tmp_path: Path) -> None:
    path = touch(tmp_path / "exp" / "files" / "sub" / "plan.md")

    [row] = read_file(tmp_path, "{experiment}/files/", path)

    assert row == {
        "experiment": "exp",
        "filename": "sub/plan.md",
        "path": "exp/files/sub/plan.md",
        "ctime": row["ctime"],
        "mtime": "2026-10-18T00:00:00Z",
        "mtime_ns": 1_792_281_600_123_456_789,
        "content": "x",
    }
    assert str(row["ctime"]).endswith("Z")


def test_names_a_file_from_its_folder_under_a_glob(tmp_path: Path) -> None:
    path = touch(tmp_path / "notes" / "exp" / "plan.md")

    [row] = read_file(tmp_path, "notes/{experiment}/*.md", path)

    assert (row["experiment"], row["filename"]) == ("exp", "plan.md")


@pytest.mark.parametrize("relative", ["exp/other/plan.md", "exp/files", "loose.md"])
def test_skips_a_path_outside_the_template(tmp_path: Path, relative: str) -> None:
    assert read_file(tmp_path, "{experiment}/files/", touch(tmp_path / relative)) == []

