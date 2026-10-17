from pathlib import Path

import pytest

from labnotes.find_config import find_config
from labnotes.models import LabnotesConfig


def write(folder: Path, text: str) -> Path:
    path = folder / ".labnotes.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_finds_nothing_without_a_config(tmp_path: Path) -> None:
    assert find_config(tmp_path) is None


def test_an_empty_config_uses_the_default_folders(tmp_path: Path) -> None:
    path = write(tmp_path, "")

    assert find_config(tmp_path) == LabnotesConfig(
        path, tmp_path / "experiments", tmp_path / "data"
    )


def test_finds_the_config_in_a_parent_folder(tmp_path: Path) -> None:
    path = write(tmp_path, "")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    config = find_config(nested)

    assert config is not None
    assert config.path == path
    assert config.data_folder == tmp_path / "data"


def test_the_nearest_config_wins(tmp_path: Path) -> None:
    write(tmp_path, "")
    nested = tmp_path / "a"
    nested.mkdir()
    path = write(nested, "")

    config = find_config(nested)

    assert config is not None
    assert config.path == path


def test_ignores_a_folder_named_like_the_config(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").mkdir()

    assert find_config(tmp_path) is None


def test_resolves_relative_folders_against_the_config(tmp_path: Path) -> None:
    write(tmp_path, 'experiments = "notes/exp"\ndata = "../runs"\n')
    nested = tmp_path / "a"
    nested.mkdir()

    config = find_config(nested)

    assert config is not None
    assert config.experiments_folder == tmp_path / "notes" / "exp"
    assert config.data_folder == tmp_path / "../runs"


def test_keeps_absolute_folders(tmp_path: Path) -> None:
    write(tmp_path, 'data = "/srv/runs"\n')

    config = find_config(tmp_path)

    assert config is not None
    assert config.data_folder == Path("/srv/runs")


def test_expands_the_home_folder(tmp_path: Path) -> None:
    write(tmp_path, 'data = "~/runs"\n')

    config = find_config(tmp_path)

    assert config is not None
    assert config.data_folder == Path.home() / "runs"


def test_rejects_unknown_keys(tmp_path: Path) -> None:
    path = write(tmp_path, 'data = "d"\nexperiment = "e"\nzz = 1\n')

    with pytest.raises(ValueError) as error:
        find_config(tmp_path)

    assert str(error.value) == f"{path}: unknown keys experiment, zz"


def test_rejects_a_folder_that_is_not_a_string(tmp_path: Path) -> None:
    path = write(tmp_path, "experiments = 1\n")

    with pytest.raises(ValueError) as error:
        find_config(tmp_path)

    assert str(error.value) == f"{path}: experiments must be a string"


def test_rejects_invalid_toml(tmp_path: Path) -> None:
    write(tmp_path, "data = \n")

    with pytest.raises(ValueError):
        find_config(tmp_path)
