from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.summarize_config import summarize_config


@pytest.fixture(autouse=True)
def default_counts() -> Iterator[None]:
    with mock.patch("labnotes.summarize_config.DEFAULT_COUNTS", "default"):
        yield


def test_summarizes_the_grid_from_params_and_repeats() -> None:
    summary = summarize_config(
        {"command": "go", "repeats": 3, "params": {"x": [1, 2], "y": ["a"], "z": 5}}
    )

    assert summary == {
        "fixed": {},
        "varies": {"x": [1, 2], "y": ["a"], "z": [5]},
        "cell_count": 2,
        "runs_per_cell": 3,
        "target": 6,
        "completed_run": "default",
        "mode": "fill",
        "other": {"command": "go"},
    }


def test_has_no_target_for_an_adhoc_grid() -> None:
    summary = summarize_config({"command": "go", "repeats": 3, "mode": "adhoc"})

    assert (summary["mode"], summary["runs_per_cell"], summary["target"]) == (
        "adhoc",
        3,
        None,
    )


def test_defaults_to_one_repeat() -> None:
    summary = summarize_config({"command": "go"})

    assert (summary["runs_per_cell"], summary["target"]) == (1, 1)


@pytest.mark.parametrize("config", [None, {}, {"repeats": "two", "params": [1]}])
def test_has_no_grid_without_a_usable_config(config: dict[str, object] | None) -> None:
    summary = summarize_config(config)

    assert (summary["varies"], summary["runs_per_cell"], summary["target"]) == (
        {},
        None,
        None,
    )
    assert summary["other"] == {}


def test_takes_counts_from_the_config() -> None:
    summary = summarize_config({"command": "go", "counts": "exit_code = 0"})

    assert summary["completed_run"] == "exit_code = 0"


def test_ignores_counts_that_is_not_a_string() -> None:
    assert summarize_config({"counts": 1})["completed_run"] == "default"
