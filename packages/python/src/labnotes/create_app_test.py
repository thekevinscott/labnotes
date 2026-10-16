import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.create_app import create_app

EXPERIMENT: dict[str, object] = {
    "name": "models-effort",
    "study": "v2-model-effort",
    "fixed": {"tests": True},
    "varies": {"model": ["opus", "haiku"]},
    "cell_count": 2,
    "runs_per_cell": 3,
    "target": 6,
    "completed_run": "exit_code = 0",
    "other": {"script": "run.py"},
    "runs": 4,
    "completed": 3,
    "filled": 3,
    "cells": [
        {"values": {"model": "opus"}, "runs": 3, "completed": 3},
        {"values": {"model": "haiku"}, "runs": 1, "completed": 0},
    ],
    "missing_columns": [],
    "notes": [{"name": "PLAN.md", "html": "<h1>The plan</h1>"}],
    "runs_list": [
        {"labnotes_completed": 1, "run_id": "r1", "model": "opus", "result": "x" * 100}
    ],
    "run_columns": ["run_id", "model"],
}


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.create_app.open_experiments") as open_experiments,
        mock.patch("labnotes.create_app.open_runs") as open_runs,
        mock.patch(
            "labnotes.create_app.drain_watch", new_callable=mock.AsyncMock
        ) as drain,
        mock.patch(
            "labnotes.create_app.list_experiments",
            new_callable=mock.AsyncMock,
            return_value=[EXPERIMENT],
        ) as list_experiments,
        mock.patch(
            "labnotes.create_app.load_experiment",
            new_callable=mock.AsyncMock,
            return_value=EXPERIMENT,
        ) as load_experiment,
    ):
        for opener in (open_experiments, open_runs):
            opener.return_value.ready = mock.AsyncMock()
        yield {
            "open_experiments": open_experiments,
            "open_runs": open_runs,
            "drain_watch": drain,
            "list_experiments": list_experiments,
            "load_experiment": load_experiment,
        }


@pytest.fixture
def app(collaborators: dict[str, mock.MagicMock]) -> Iterator[Any]:
    app = create_app(Path("exp"), Path("data"))

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)

    asyncio.run(run_lifespan())
    yield app


def call(app: Any, path: str, **path_params: str) -> tuple[int, str]:
    [endpoint] = [
        route.endpoint for route in app.routes if getattr(route, "path", None) == path
    ]
    request = mock.Mock(scope={"type": "http"}, path_params=path_params)
    request.app = app
    request.url_for = lambda route, /, **params: f"/{route}/{params.get('name', '')}"
    response = asyncio.run(endpoint(request))
    return response.status_code, response.body.decode()


def test_opens_both_folders_and_watches_them(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    experiments = collaborators["open_experiments"].return_value
    runs = collaborators["open_runs"].return_value
    collaborators["open_experiments"].assert_called_once_with(Path("exp"))
    collaborators["open_runs"].assert_called_once_with(Path("data"))
    experiments.ready.assert_awaited_once()
    runs.ready.assert_awaited_once()
    watched = [call.args[0] for call in collaborators["drain_watch"].await_args_list]
    assert watched == [experiments, runs]


def test_index_lists_experiments_with_progress(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    status, text = call(app, "/")

    assert status == 200
    collaborators["list_experiments"].assert_awaited_once_with(
        app.state.experiments, app.state.runs
    )
    assert 'href="/experiment/models-effort"' in text
    assert "v2-model-effort" in text
    assert "50%" in text
    assert "--share: 0.5000" in text
    assert "1 experiment," in text
    assert "4 runs recorded" in text


def test_experiment_page_shows_design_grid_notes_and_runs(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    status, text = call(app, "/experiments/{name}", name="models-effort")

    assert status == 200
    collaborators["load_experiment"].assert_awaited_once_with(
        app.state.experiments, app.state.runs, "models-effort"
    )
    assert '<span class="chip">haiku</span>' in text
    assert '<span class="chip quiet">true</span>' in text
    assert "<code>exit_code = 0</code>" in text
    assert "<h1>The plan</h1>" in text
    assert '<td class="cell done"' in text
    assert '<td class="cell"' in text
    assert "<pre>" + "x" * 100 + "</pre>" in text
    assert '<span class="status good"' in text


def test_unknown_experiment_is_not_found(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_experiment"].return_value = None

    with pytest.raises(Exception) as raised:
        call(app, "/experiments/{name}", name="nope")
    assert getattr(raised.value, "status_code", None) == 404


def test_mounts_the_stylesheet_folder(app: Any) -> None:
    [static] = [
        route for route in app.routes if getattr(route, "name", None) == "static"
    ]
    assert static.app.directory == Path(__file__).parent / "static"
