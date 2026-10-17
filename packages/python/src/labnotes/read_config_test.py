from pathlib import Path

import pytest

from labnotes.models import LabnotesConfig
from labnotes.read_config import read_config


def write(folder: Path, text: str) -> Path:
    path = folder / ".labnotes.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_an_empty_config_uses_the_default_folders(tmp_path: Path) -> None:
    path = write(tmp_path, "")

    assert read_config(path) == LabnotesConfig(
        path, tmp_path / "experiments", tmp_path / "data"
    )


def test_resolves_relative_folders_against_the_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path, 'experiments = "notes/exp"\ndata = "../runs"\n')
    monkeypatch.chdir(tmp_path)

    config = read_config(Path(".labnotes.toml"))

    assert config.path == tmp_path / ".labnotes.toml"
    assert config.experiments_folder == tmp_path / "notes" / "exp"
    assert config.data_folder == tmp_path / "../runs"


def test_keeps_absolute_folders(tmp_path: Path) -> None:
    config = read_config(write(tmp_path, 'data = "/srv/runs"\n'))

    assert config.data_folder == Path("/srv/runs")


def test_expands_the_home_folder(tmp_path: Path) -> None:
    config = read_config(write(tmp_path, 'data = "~/runs"\n'))

    assert config.data_folder == Path.home() / "runs"


def test_rejects_unknown_keys(tmp_path: Path) -> None:
    path = write(tmp_path, 'data = "d"\nexperiment = "e"\nzz = 1\n')

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value) == f"{path}: unknown keys experiment, zz"


def test_rejects_a_folder_that_is_not_a_string(tmp_path: Path) -> None:
    path = write(tmp_path, "experiments = 1\n")

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value) == f"{path}: experiments must be a string"


def test_rejects_invalid_toml(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        read_config(write(tmp_path, "data = \n"))
