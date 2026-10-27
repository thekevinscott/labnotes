import typing
from collections.abc import Callable
from pathlib import Path

from labnotes.models import Controls, ExperimentConfig, LabnotesConfig, RunView


def test_a_run_view_starts_unsorted_and_unfiltered() -> None:
    view = RunView()

    assert (view.sort, view.descending, view.status) == (None, False, None)
    assert (view.filters, view.picked) == ({}, {})


def test_run_views_do_not_share_their_picks() -> None:
    view = RunView()
    view.picked["model"] = {"a": '"a"'}

    assert RunView().picked == {}


def test_set_concurrency_takes_a_number() -> None:
    hint = typing.get_type_hints(Controls)["set_concurrency"]

    assert hint == Callable[[int], None]


def test_a_config_holds_many_experiments_by_default() -> None:
    config = LabnotesConfig(Path("/p/.labnotes.toml"), Path("/p"), "e", "f", "r")

    assert config.experiment is None


def test_configs_do_not_share_their_defaults() -> None:
    config = LabnotesConfig(Path("/p/.labnotes.toml"), Path("/p"), "e", "f", "r")
    config.defaults["command"] = "go"

    assert LabnotesConfig(Path("/p"), Path("/p"), "e", "f", "r").defaults == {}


def test_configs_default_to_the_default_retries() -> None:
    project = LabnotesConfig(Path("/p/.labnotes.toml"), Path("/p"), "e", "f", "r")
    experiment = ExperimentConfig("run", 1, {})

    assert (project.retries, experiment.retries) == (2, 2)


def test_an_experiment_has_no_meta_command_by_default() -> None:
    assert ExperimentConfig("run", 1, {}).meta is None


def test_an_experiment_has_no_setup_or_teardown_by_default() -> None:
    experiment = ExperimentConfig("run", 1, {})

    assert (experiment.setup, experiment.teardown) == (None, None)


def test_experiments_default_to_the_default_memory_interval() -> None:
    assert ExperimentConfig("run", 1, {}).memory_interval == 5.0


def test_experiments_do_not_share_environment_defaults() -> None:
    first = ExperimentConfig("run", 1, {})
    first.env["FOO"] = "one"
    assert ExperimentConfig("run", 1, {}).env == {}
