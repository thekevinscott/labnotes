import pytest

from labnotes.summarize_config import COMPLETED_RUN, summarize_config


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
        "completed_run": COMPLETED_RUN,
        "other": {"command": "go"},
    }


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


def test_counts_runs_the_runner_counts() -> None:
    assert COMPLETED_RUN == "exit_code = 0 AND NOT coalesce(excluded, 0)"
