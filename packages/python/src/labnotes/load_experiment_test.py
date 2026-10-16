import asyncio
import json
from collections.abc import Iterator
from typing import cast
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
            return_value=["run_id", "x", "study"],
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
        mock.patch("labnotes.load_experiment.parse_run_view") as parse_run_view,
        mock.patch(
            "labnotes.load_experiment.sort_href",
            side_effect=lambda view, column: f"?sort={column}",
        ) as sort_href,
        mock.patch(
            "labnotes.load_experiment.render_markdown",
            side_effect=lambda text, outputs: f"<p>{text}{''.join(outputs)}</p>",
        ),
        mock.patch(
            "labnotes.load_experiment.python_blocks", return_value=["a = 1\n"]
        ) as python_blocks,
    ):
        yield {
            "run_columns": run_columns,
            "study_progress": study_progress,
            "list_runs": list_runs,
            "parse_run_view": parse_run_view,
            "sort_href": sort_href,
            "python_blocks": python_blocks,
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

    loaded = asyncio.run(
        load_experiment(experiments, runs, "it's", {"sort": "x", "f.study": "s"})
    )

    assert loaded is not None
    assert (loaded["name"], loaded["study"], loaded["target"]) == ("a", "s1", 4)
    assert (loaded["runs"], loaded["filled"]) == (3, 2)
    assert loaded["notes"] == [
        {"name": "PLAN.md", "html": "<p>plan</p>", "runnable": True}
    ]
    assert loaded["runs_list"] == [{"labnotes_completed": 1, "run_id": "r1"}]
    assert loaded["run_columns"] == ["run_id", "x"]
    first, second = experiments.query.await_args_list
    assert first.args[0].endswith("WHERE name = 'it''s'")
    assert "WHERE experiment = 'it''s' ORDER BY name" in second.args[0]
    params = {"sort": "x", "f.study": "s"}
    view = collaborators["parse_run_view"].return_value
    collaborators["parse_run_view"].assert_called_once_with(params, ["run_id", "x"])
    collaborators["list_runs"].assert_awaited_once_with(runs, "s1", "1", view)
    assert loaded["run_view"] is view
    assert loaded["sort_hrefs"] == {
        "status": "?sort=status",
        "run_id": "?sort=run_id",
        "x": "?sort=x",
    }
    assert collaborators["sort_href"].call_args_list[0].args == (view, "status")
    progress_args = collaborators["study_progress"].await_args.args
    assert progress_args[1] == "s1"
    assert progress_args[3] == ["run_id", "x", "study"]


def test_skips_runs_for_an_experiment_without_a_study(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    experiments = make_experiments([{"name": "a", "study": None, "design": "{}"}])

    loaded = asyncio.run(load_experiment(experiments, mock.Mock(), "a", {}))

    assert loaded is not None
    assert loaded["runs_list"] == []
    assert collaborators["study_progress"].await_args.args[1] is None
    collaborators["list_runs"].assert_not_awaited()


def test_returns_none_for_an_unknown_experiment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert (
        asyncio.run(load_experiment(make_experiments([]), mock.Mock(), "nope", {}))
        is None
    )


def test_lists_a_varies_key_that_is_the_first_column_once(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["run_columns"].return_value = ["x", "study"]
    experiments = make_experiments(
        [{"name": "a", "study": "s1", "design": json.dumps(DESIGN)}]
    )

    loaded = asyncio.run(load_experiment(experiments, mock.Mock(), "a", {}))

    assert loaded is not None
    assert loaded["run_columns"] == ["x"]


def test_renders_notes_with_their_saved_outputs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    experiments = make_experiments([{"name": "a", "study": None, "design": "{}"}])
    seen: list[tuple[str, str]] = []

    def outputs_for(note: str, content: str) -> list[str]:
        seen.append((note, content))
        return ["<out>"]

    loaded = asyncio.run(
        load_experiment(experiments, mock.Mock(), "a", {}, outputs_for)
    )

    assert loaded is not None
    assert loaded["notes"] == [
        {"name": "PLAN.md", "html": "<p>plan<out></p>", "runnable": True}
    ]
    assert seen == [("PLAN.md", "plan")]


def test_marks_notes_without_python_blocks_as_not_runnable(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["python_blocks"].return_value = []
    experiments = make_experiments([{"name": "a", "study": None, "design": "{}"}])

    loaded = asyncio.run(load_experiment(experiments, mock.Mock(), "a", {}))

    assert loaded is not None
    notes = cast(list[dict[str, object]], loaded["notes"])
    assert notes[0]["runnable"] is False
    collaborators["python_blocks"].assert_called_once_with("plan")
