import tomllib
from pathlib import Path
from unittest import mock

import pytest

from labnotes.copy_experiment import copy_experiment
from labnotes.create_experiment import STARTER, create_experiment


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_config(root: Path) -> mock.Mock:
    return mock.Mock(
        experiment=None,
        root=root,
        experiments="notes/{experiment}",
        runs="data/{experiment}/{run}",
    )


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


def test_writes_the_flags_into_the_starter(tmp_path: Path) -> None:
    path = create_experiment(
        make_config(tmp_path), "study", None, "go {run_dir}", 3, {"m": ["a"]}
    )

    assert tomllib.loads((path / "experiment.toml").read_text()) == {
        "command": "go {run_dir}",
        "repeats": 3,
        "params": {"m": ["a"]},
    }


def test_copies_another_experiment(tmp_path: Path) -> None:
    write(tmp_path / "notes/base/experiment.toml", 'command = "go"\nrepeats = 2\n')
    write(tmp_path / "notes/base/files/plan.md", "plan")
    with mock.patch(
        "labnotes.create_experiment.copy_experiment", wraps=copy_experiment
    ) as copy:
        path = create_experiment(make_config(tmp_path), "study", "base", None, 4)

    copy.assert_called_once_with(tmp_path / "notes/base", path, tmp_path / "data/base")
    assert (path / "files/plan.md").read_text() == "plan"
    assert (path / "experiment.toml").read_text() == (
        'from = "base"\ncommand = "go"\nrepeats = 4\n'
    )


@pytest.mark.parametrize("made", [False, True])
def test_refuses_a_source_without_a_definition(tmp_path: Path, made: bool) -> None:
    if made:
        write(tmp_path / "notes/base/plan.md", "plan")

    with pytest.raises(ValueError, match="No experiment.toml for base at "):
        create_experiment(make_config(tmp_path), "study", "base")

    assert not (tmp_path / "notes/study").exists()


def test_refuses_an_existing_experiment_before_copying(tmp_path: Path) -> None:
    write(tmp_path / "notes/base/experiment.toml", 'command = "go"\n')
    (tmp_path / "notes/study").mkdir()

    with pytest.raises(ValueError, match="study already exists at"):
        create_experiment(make_config(tmp_path), "study", "base")

    assert list((tmp_path / "notes/study").iterdir()) == []
