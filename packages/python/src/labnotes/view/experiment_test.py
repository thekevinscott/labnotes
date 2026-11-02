import dataclasses
from pathlib import Path

import pytest

from labnotes.view.experiment import Experiment


def test_holds_the_root_name_and_runs() -> None:
    experiment = Experiment(Path("/p"), "alpha", {"alpha/runs/a": {"id": "a"}})

    assert experiment.root == Path("/p")
    assert experiment.name == "alpha"
    assert experiment.runs == {"alpha/runs/a": {"id": "a"}}


def test_is_frozen() -> None:
    experiment = Experiment(Path("/p"), "alpha", {})

    with pytest.raises(dataclasses.FrozenInstanceError):
        experiment.name = "beta"  # type: ignore[misc]
