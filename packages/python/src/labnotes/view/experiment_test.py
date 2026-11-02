import dataclasses
from pathlib import Path

import pytest

from labnotes.view.experiment import Experiment


def test_holds_the_root_name_and_runs() -> None:
    runs = ({"folder": "alpha/runs/a", "id": "a"},)
    experiment = Experiment(Path("/p"), "alpha", runs)

    assert experiment.root == Path("/p")
    assert experiment.name == "alpha"
    assert experiment.runs == runs


def test_defaults_to_an_empty_read_only_config() -> None:
    experiment = Experiment(Path("/p"), "alpha", ())

    assert experiment.config == {}
    with pytest.raises(TypeError):
        experiment.config["x"] = 1  # type: ignore[index]


def test_holds_the_config() -> None:
    experiment = Experiment(Path("/p"), "alpha", (), {"command": "go"})

    assert experiment.config == {"command": "go"}


def test_holds_data_only() -> None:
    assert [field.name for field in dataclasses.fields(Experiment)] == [
        "root",
        "name",
        "runs",
        "config",
    ]


def test_is_frozen() -> None:
    experiment = Experiment(Path("/p"), "alpha", ())

    with pytest.raises(dataclasses.FrozenInstanceError):
        experiment.name = "beta"  # type: ignore[misc]
