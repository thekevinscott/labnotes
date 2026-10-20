import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest import mock

import pytest

from labnotes.load_experiment import load_experiment

CONFIG = {
    "command": "go",
    "repeats": 2,
    "mode": "fill",
    "params": {"x": [1, 2], "y": ["a"]},
}
ROOT = Path("/p")


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.load_experiment.count_runs",
            new_callable=mock.AsyncMock,
            return_value=[{"runs": 3, "completed": 2}],
        ) as count_runs,
        mock.patch(
            "labnotes.load_experiment.experiment_notes",
            new_callable=mock.AsyncMock,
            return_value=[{"name": "PLAN.md", "content": "plan"}],
        ) as experiment_notes,
        mock.patch(
            "labnotes.load_experiment.list_runs",
            new_callable=mock.AsyncMock,
            return_value=[{"labnotes_completed": 1, "id": "r1"}],
        ) as list_runs,
        mock.patch(
            "labnotes.load_experiment.check_counts",
            new_callable=mock.AsyncMock,
            side_effect=lambda tables, source, summary: {
                **summary,
                "completed_run": "checked",
            },
        ) as check_counts,
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
            "count_runs": count_runs,
            "experiment_notes": experiment_notes,
            "list_runs": list_runs,
            "parse_run_view": parse_run_view,
            "check_counts": check_counts,
            "sort_href": sort_href,
            "python_blocks": python_blocks,
        }


def make_tables(found: list[dict[str, object]]) -> mock.Mock:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=found)
    return tables


def experiment(config: dict[str, object] | None = CONFIG) -> list[dict[str, object]]:
    text = None if config is None else json.dumps(config)
    return [{"name": "a", "display_name": "Alpha", "config": text, "source": "toml"}]


def test_loads_config_notes_progress_and_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    tables = make_tables(experiment())
    params = {"sort": "x", "f.x": "1"}

    loaded = asyncio.run(load_experiment(tables, ROOT, "adhoc", "it's", params))

    assert loaded is not None
    assert (loaded["name"], loaded["display_name"], loaded["target"]) == (
        "a",
        "Alpha",
        4,
    )
    assert (loaded["runs"], loaded["completed"]) == (3, 2)
    assert (loaded["config_source"], loaded["counts_set"]) == ("toml", False)
    assert loaded["notes"] == [
        {"name": "PLAN.md", "html": "<p>plan</p>", "runnable": True}
    ]
    assert loaded["runs_list"] == [{"labnotes_completed": 1, "id": "r1"}]
    assert loaded["run_columns"] == ["id", "x", "y"]
    assert tables.query.await_args.args[0] == (
        "SELECT name, display_name, config, source FROM experiments"
        " WHERE name = 'it''s'"
    )
    collaborators["experiment_notes"].assert_awaited_once_with(tables, ROOT, "it's")
    view = collaborators["parse_run_view"].return_value
    collaborators["parse_run_view"].assert_called_once_with(params, ["id", "x", "y"])
    source = collaborators["list_runs"].await_args.args[1]
    assert source.endswith("FROM runs WHERE experiment = 'it''s')")
    assert '"x", params' in source
    collaborators["list_runs"].assert_awaited_once_with(tables, source, "checked", view)
    checked = collaborators["check_counts"].await_args.args
    assert checked[:2] == (tables, source)
    assert checked[2]["completed_run"] == (
        "exit_code = 0 AND NOT coalesce(run ->> 'excluded', false)"
    )
    collaborators["count_runs"].assert_awaited_once_with(tables, source, "checked")
    assert loaded["run_view"] is view
    assert loaded["sort_hrefs"] == {
        "status": "?sort=status",
        "id": "?sort=id",
        "x": "?sort=x",
        "y": "?sort=y",
    }
    assert collaborators["sort_href"].call_args_list[0].args == (view, "status")


def test_shows_only_id_without_a_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    loaded = asyncio.run(
        load_experiment(make_tables(experiment(None)), ROOT, "adhoc", "a", {})
    )

    assert loaded is not None
    assert (loaded["run_columns"], loaded["target"]) == (["id"], None)


def test_falls_back_to_the_project_mode(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    config = {key: value for key, value in CONFIG.items() if key != "mode"}

    loaded = asyncio.run(
        load_experiment(make_tables(experiment(config)), ROOT, "fill", "a", {})
    )

    assert loaded is not None
    assert (loaded["mode"], loaded["target"]) == ("fill", 4)


def test_returns_none_for_an_unknown_experiment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert (
        asyncio.run(load_experiment(make_tables([]), ROOT, "adhoc", "nope", {})) is None
    )


def test_lists_a_param_named_id_once(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    config = {**CONFIG, "params": {"id": [1], "a": [2]}}

    loaded = asyncio.run(
        load_experiment(make_tables(experiment(config)), ROOT, "adhoc", "a", {})
    )

    assert loaded is not None
    assert loaded["run_columns"] == ["id", "a"]


def test_renders_notes_with_their_saved_outputs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    seen: list[tuple[str, str]] = []

    def outputs_for(note: str, content: str) -> list[str]:
        seen.append((note, content))
        return ["<out>"]

    loaded = asyncio.run(
        load_experiment(make_tables(experiment()), ROOT, "adhoc", "a", {}, outputs_for)
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

    loaded = asyncio.run(
        load_experiment(make_tables(experiment()), ROOT, "adhoc", "a", {})
    )

    assert loaded is not None
    notes = cast(list[dict[str, object]], loaded["notes"])
    assert notes[0]["runnable"] is False
    collaborators["python_blocks"].assert_called_once_with("plan")


def test_notes_a_counts_rule_set_in_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    config = {**CONFIG, "counts": "exit_code = 0"}

    loaded = asyncio.run(
        load_experiment(make_tables(experiment(config)), ROOT, "adhoc", "a", {})
    )

    assert loaded is not None
    assert loaded["counts_set"] is True


def test_has_no_counts_rule_without_a_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    loaded = asyncio.run(
        load_experiment(make_tables(experiment(None)), ROOT, "adhoc", "a", {})
    )

    assert loaded is not None
    assert loaded["counts_set"] is False
