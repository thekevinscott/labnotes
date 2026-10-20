from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.create_note import create_note


@pytest.fixture
def config(tmp_path: Path) -> Any:
    (tmp_path / "alpha").mkdir()
    return mock.Mock(
        root=tmp_path, experiments="{experiment}", files="{experiment}/notes/deep/*.md"
    )


def test_creates_an_untitled_note_in_the_experiments_files_folder(
    config: Any,
) -> None:
    assert create_note(config, "alpha") == "Untitled.md"

    note = config.root / "alpha/notes/deep/Untitled.md"
    assert note.read_text(encoding="utf-8") == "# Untitled\n"


@pytest.mark.parametrize("taken", [1, 2, 3])
def test_numbers_the_name_past_existing_notes(config: Any, taken: int) -> None:
    names = ["Untitled.md", "Untitled 2.md", "Untitled 3.md", "Untitled 4.md"]
    notes = config.root / "alpha/notes/deep"
    notes.mkdir(parents=True)
    for name in names[:taken]:
        (notes / name).write_text("mine", encoding="utf-8")

    assert create_note(config, "alpha") == names[taken]
    assert (notes / names[0]).read_text(encoding="utf-8") == "mine"
    assert (notes / names[taken]).read_text(encoding="utf-8") == "# Untitled\n"


@pytest.mark.parametrize("experiment", ["missing", "..", ".hidden"])
def test_refuses_an_experiment_that_is_not_a_folder_under_the_root(
    config: Any, experiment: str
) -> None:
    (config.root / ".hidden").mkdir()

    assert create_note(config, experiment) is None
    assert not (config.root.parent / "notes").exists()
    assert not (config.root / "missing").exists()
    assert not (config.root / ".hidden/notes").exists()
