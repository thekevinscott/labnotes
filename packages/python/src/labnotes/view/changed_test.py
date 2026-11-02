import subprocess
import sys
from pathlib import Path

import pytest

from labnotes import view
from labnotes.view.changed import Changed
from labnotes.view.experiment import Experiment

EXPERIMENT = Experiment(Path("/p"), "alpha", {})


def test_carries_the_experiment_and_the_changed_paths() -> None:
    message = Changed(EXPERIMENT, frozenset({"alpha/runs/a/stdout.log"}))

    assert message.experiment is EXPERIMENT
    assert message.paths == {"alpha/runs/a/stdout.log"}


def test_defaults_to_no_paths() -> None:
    assert Changed(None).paths == frozenset()


def test_is_handled_as_on_labnotes_changed_and_does_not_bubble() -> None:
    assert Changed(None).handler_name == "on_labnotes_changed"
    assert Changed.bubble is False


def test_is_exported_from_the_view_package() -> None:
    assert view.Changed is Changed
    assert view.Experiment is Experiment
    assert view.__all__ == ["Changed", "Experiment", "serve"]


def test_the_view_package_names_what_it_lacks() -> None:
    with pytest.raises(AttributeError, match="'labnotes.view' has no attribute 'nope'"):
        getattr(view, "nope")


def test_importing_the_view_package_leaves_textual_unloaded() -> None:
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            "import labnotes.view, sys; print('textual' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert loaded.stdout == "False\n"
