from pathlib import Path

from labnotes.view.changed import Changed, Experiment

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
