import asyncio
import json
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.load_experiment import load_experiment

DESIGN = {"study": "s1", "runs_per_cell": 2, "varies": {"x": [1, 2], "y": ["a"]}}


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.load_experiment.run_columns",
            new_callable=mock.AsyncMock,
            return_value=["run_id", "study", "x"],
        ) as run_columns,
        mock.patch(
            "labnotes.load_experiment.study_progress",
            new_callable=mock.AsyncMock,
            return_value={"runs": 3, "filled": 2},
        ) as study_progress,
        mock.patch(
            "labnotes.load_experiment.list_runs",
            new_callable=mock.AsyncMock,
            return_value=[{"labnotes_completed": 1, "run_id": "r1"}],
        ) as list_runs,
        mock.patch(
            "labnotes.load_experiment.render_markdown",
            side_effect=lambda text: f"<p>{text}</p>",
        ),
    ):
        yield {
            "run_columns": run_columns,
            "study_progress": study_progress,
            "list_runs": list_runs,
        }


def make_experiments(found: list[dict[str, object]]) -> mock.Mock:
    experiments = mock.Mock()
    experiments.query = mock.AsyncMock(
        side_effect=[found, [{"name": "PLAN.md", "content": "plan"}]]
    )
    return experiments


def test_loads_design_notes_progress_and_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    experiments = make_experiments(
        [{"name": "a", "study": "s1", "design": json.dumps(DESIGN)}]
    )
    runs = mock.Mock()

    loaded = asyncio.run(load_experiment(experiments, runs, "it's"))

    assert loaded is not None
    assert (loaded["name"], loaded["study"], loaded["target"]) == ("a", "s1", 4)
    assert (loaded["runs"], loaded["filled"]) == (3, 2)
    assert loaded["notes"] == [{"name": "PLAN.md", "html": "<p>plan</p>"}]
    assert loaded["runs_list"] == [{"labnotes_completed": 1, "run_id": "r1"}]
    assert loaded["run_columns"] == ["run_id", "x"]
    first, second = experiments.query.await_args_list
    assert first.args[0].endswith("WHERE name = 'it''s'")
    assert "WHERE experiment = 'it''s' ORDER BY name" in second.args[0]
    collaborators["list_runs"].assert_awaited_once_with(runs, "s1", "1")
    progress_args = collaborators["study_progress"].await_args.args
    assert progress_args[1] == "s1"
    assert progress_args[3] == ["run_id", "study", "x"]


def test_skips_runs_for_an_experiment_without_a_study(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    experiments = make_experiments([{"name": "a", "study": None, "design": "{}"}])

    loaded = asyncio.run(load_experiment(experiments, mock.Mock(), "a"))

    assert loaded is not None
    assert loaded["runs_list"] == []
    assert collaborators["study_progress"].await_args.args[1] is None
    collaborators["list_runs"].assert_not_awaited()


def test_returns_none_for_an_unknown_experiment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert (
        asyncio.run(load_experiment(make_experiments([]), mock.Mock(), "nope")) is None
    )
