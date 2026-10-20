from pathlib import Path

import pytest

from labnotes.create_note import create_note
from labnotes.models import LabnotesConfig


@pytest.fixture
def config(tmp_path: Path) -> LabnotesConfig:
    (tmp_path / "alpha").mkdir()
    return LabnotesConfig(
        path=tmp_path / ".labnotes.toml",
        root=tmp_path,
        experiments="{experiment}",
        files="{experiment}/notes/*.md",
        runs="{experiment}/runs/{run}",
    )


def test_creates_an_untitled_note_in_the_experiments_files_folder(
    config: LabnotesConfig,
) -> None:
    assert create_note(config, "alpha") == "Untitled.md"

    note = config.root / "alpha/notes/Untitled.md"
    assert note.read_text(encoding="utf-8") == "# Untitled\n"


def test_numbers_the_name_past_existing_notes(config: LabnotesConfig) -> None:
    notes = config.root / "alpha/notes"
    notes.mkdir()
    (notes / "Untitled.md").write_text("mine", encoding="utf-8")
    (notes / "Untitled 2.md").write_text("mine", encoding="utf-8")

    assert create_note(config, "alpha") == "Untitled 3.md"
    assert (notes / "Untitled.md").read_text(encoding="utf-8") == "mine"
    assert (notes / "Untitled 3.md").read_text(encoding="utf-8") == "# Untitled\n"


@pytest.mark.parametrize("experiment", ["missing", "..", ".hidden"])
def test_refuses_an_experiment_that_is_not_a_folder_under_the_root(
    config: LabnotesConfig, experiment: str
) -> None:
    (config.root / ".hidden").mkdir()

    assert create_note(config, experiment) is None
    assert not (config.root / "files").exists()
    assert not (config.root / ".hidden/notes").exists()
