import dataclasses
from pathlib import Path

import pytest

from labnotes.view.experiment import Experiment, Group


def test_holds_the_root_name_and_runs() -> None:
    experiment = Experiment(Path("/p"), "alpha", {"alpha/runs/a": {"id": "a"}})

    assert experiment.root == Path("/p")
    assert experiment.name == "alpha"
    assert experiment.runs == {"alpha/runs/a": {"id": "a"}}


def test_defaults_to_an_empty_read_only_config_not_live_and_ungrouped() -> None:
    experiment = Experiment(Path("/p"), "alpha", {})

    assert experiment.config == {}
    with pytest.raises(TypeError):
        experiment.config["x"] = 1  # type: ignore[index]
    assert experiment.live is False
    assert experiment.groups is None


def test_holds_the_config_liveness_and_groups() -> None:
    groups = (Group("inv", ("alpha/runs/inv/a",), False),)
    experiment = Experiment(Path("/p"), "alpha", {}, {"command": "go"}, True, groups)

    assert experiment.config == {"command": "go"}
    assert experiment.live is True
    assert experiment.groups == groups


def test_holds_data_only() -> None:
    assert [field.name for field in dataclasses.fields(Experiment)] == [
        "root",
        "name",
        "runs",
        "config",
        "live",
        "groups",
    ]


def test_is_frozen() -> None:
    experiment = Experiment(Path("/p"), "alpha", {})

    with pytest.raises(dataclasses.FrozenInstanceError):
        experiment.name = "beta"  # type: ignore[misc]
