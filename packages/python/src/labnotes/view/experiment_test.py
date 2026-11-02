import dataclasses
from pathlib import Path

import pytest

from labnotes.view.experiment import Experiment


def test_holds_the_root_name_and_runs() -> None:
    experiment = Experiment(Path("/p"), "alpha", {"alpha/runs/a": {"id": "a"}})

    assert experiment.root == Path("/p")
    assert experiment.name == "alpha"
    assert experiment.runs == {"alpha/runs/a": {"id": "a"}}


def test_defaults_to_no_columns_groups_live_runs_or_runs_view() -> None:
    experiment = Experiment(Path("/p"), "alpha", {})

    assert experiment.columns == ()
    assert experiment.groups is None
    assert experiment.live is False
    assert experiment.runs_view is None


def test_holds_the_columns_groups_liveness_and_runs_view() -> None:
    groups = ({"name": "inv", "runs": [{"id": "inv/a"}]},)
    experiment = Experiment(
        Path("/p"), "alpha", {}, ("id", "m"), groups, True, "uv run view.py"
    )

    assert experiment.columns == ("id", "m")
    assert experiment.groups == groups
    assert experiment.live is True
    assert experiment.runs_view == "uv run view.py"


def test_is_frozen() -> None:
    experiment = Experiment(Path("/p"), "alpha", {})

    with pytest.raises(dataclasses.FrozenInstanceError):
        experiment.name = "beta"  # type: ignore[misc]
