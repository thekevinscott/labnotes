from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.note_path import note_path


@pytest.fixture
def config(tmp_path: Path) -> Any:
    notes = tmp_path / "alpha/notes"
    (notes / "deep").mkdir(parents=True)
    (notes / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (notes / "deep/inner.md").write_text("# Inner\n", encoding="utf-8")
    (notes / "data.csv").write_text("a,b\n", encoding="utf-8")
    (tmp_path / "secret.md").write_text("# Secret\n", encoding="utf-8")
    return mock.Mock(root=tmp_path, files="{experiment}/notes/")


def test_finds_a_note_on_disk_without_the_index(config: Any) -> None:
    assert note_path(config, "alpha", "plan.md") == config.root / "alpha/notes/plan.md"


def test_finds_a_note_in_a_subfolder(config: Any) -> None:
    found = note_path(config, "alpha", "deep/inner.md")
    assert found == config.root / "alpha/notes/deep/inner.md"


@pytest.mark.parametrize(
    ("experiment", "note"),
    [
        ("alpha", "missing.md"),
        ("alpha", "data.csv"),
        ("alpha", "deep"),
        ("alpha", "../../secret.md"),
        ("alpha", "deep/../plan.md"),
        ("..", "secret.md"),
        ("alpha/notes", "plan.md"),
    ],
)
def test_refuses_anything_but_an_existing_note(
    config: Any, experiment: str, note: str
) -> None:
    assert note_path(config, experiment, note) is None


def test_refuses_a_path_outside_the_files_pattern(tmp_path: Path) -> None:
    (tmp_path / "alpha/other").mkdir(parents=True)
    (tmp_path / "alpha/other/plan.md").write_text("# Plan\n", encoding="utf-8")
    config = mock.Mock(root=tmp_path, files="{experiment}/notes/*.md")

    assert note_path(config, "alpha", "../other/plan.md") is None
    assert note_path(config, "alpha", "deep/plan.md") is None


@pytest.mark.parametrize(
    ("experiment", "note", "expected"),
    [
        ("alpha", "x/alpha/y.md", True),
        ("alpha", "alpha/zeta/y.md", False),
        ("zeta", "zeta/alpha/y.md", False),
    ],
)
def test_matches_the_experiment_the_pattern_reads(
    tmp_path: Path, experiment: str, note: str, expected: bool
) -> None:
    (tmp_path / note).parent.mkdir(parents=True)
    (tmp_path / note).write_text("# Note\n", encoding="utf-8")
    config = mock.Mock(root=tmp_path, files="**/{experiment}/*.md")

    found = note_path(config, experiment, note)
    assert found == (tmp_path / note if expected else None)


def test_refuses_an_absolute_note_outside_the_root(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere/alpha/x.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("# Outside\n", encoding="utf-8")
    (tmp_path / "project").mkdir()
    config = mock.Mock(root=tmp_path / "project", files="**/{experiment}/*.md")

    assert note_path(config, "alpha", str(outside)) is None
