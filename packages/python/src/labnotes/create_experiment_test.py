from pathlib import Path
from unittest import mock

import pytest

from labnotes.create_experiment import STARTER, create_experiment


def make_config(root: Path) -> mock.Mock:
    return mock.Mock(experiment=None, root=root, experiments="notes/{experiment}")


def test_creates_the_folder_with_a_starter_config(tmp_path: Path) -> None:
    path = create_experiment(make_config(tmp_path), "study")

    assert path == tmp_path / "notes" / "study"
    assert (path / "experiment.toml").read_text(encoding="utf-8") == STARTER


def test_names_it_when_no_name_is_given(tmp_path: Path) -> None:
    (tmp_path / "notes" / "taken").mkdir(parents=True)
    with mock.patch(
        "labnotes.create_experiment.new_run_id",
        side_effect=lambda taken: "free" if taken("taken") else "wrong",
    ):
        path = create_experiment(make_config(tmp_path), None)

    assert path == tmp_path / "notes" / "free"
    assert path.is_dir()


@pytest.mark.parametrize(
    ("name", "message"),
    [
        # Built at runtime like argv, so an identity check can't pass.
        ("".join(["ne", "w"]), "new is reserved"),
        ("a/b", "a/b can't be an experiment name"),
        (".hidden", ".hidden can't be an experiment name"),
    ],
)
def test_rejects_a_bad_name(tmp_path: Path, name: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_experiment(make_config(tmp_path), name)

    assert not (tmp_path / "notes").exists()


def test_refuses_an_existing_experiment(tmp_path: Path) -> None:
    (tmp_path / "notes" / "study").mkdir(parents=True)

    with pytest.raises(ValueError, match="study already exists at"):
        create_experiment(make_config(tmp_path), "study")

    assert not (tmp_path / "notes" / "study" / "experiment.toml").exists()


def test_refuses_when_the_root_is_one_experiment(tmp_path: Path) -> None:
    config = mock.Mock(experiment="study", root=tmp_path, experiments="")

    with pytest.raises(ValueError, match="is the experiment study; it can't hold"):
        create_experiment(config, "other")
