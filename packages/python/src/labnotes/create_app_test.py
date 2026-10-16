import asyncio
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.create_app import create_app


def make_view(
    sort: str | None = None,
    descending: bool = False,
    status: str | None = None,
    filters: dict[str, str] | None = None,
) -> mock.Mock:
    return mock.Mock(
        sort=sort, descending=descending, status=status, filters=filters or {}
    )


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
    "notes": [
        {"name": "PLAN.md", "html": "<h1>The plan</h1>", "runnable": True},
        {"name": "READ.md", "html": "<p>Prose</p>", "runnable": False},
    ],
    "runs_list": [
        {"labnotes_completed": 1, "run_id": "r1", "model": "opus", "result": "x" * 100}
    ],
    "run_columns": ["run_id", "model"],
    "run_view": make_view(sort="model", descending=True, filters={"model": "op"}),
    "sort_hrefs": {
        "status": "?sort=status#runs",
        "run_id": "?sort=run_id#runs",
        "model": "?sort=model#runs",
    },
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
            "labnotes.create_app.stop_idle_kernels", new_callable=mock.AsyncMock
        ) as stop_idle_kernels,
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
            "stop_idle_kernels": stop_idle_kernels,
            "list_experiments": list_experiments,
            "load_experiment": load_experiment,
        }


@pytest.fixture
def app(collaborators: dict[str, mock.MagicMock]) -> Iterator[Any]:
    app = create_app(Path("exp"), Path("data"), 30)

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)

    asyncio.run(run_lifespan())
    yield app


def call(app: Any, path: str, **path_params: str) -> tuple[int, str]:
    [endpoint] = [
        route.endpoint for route in app.routes if getattr(route, "path", None) == path
    ]
    request = mock.Mock(
        scope={"type": "http"}, path_params=path_params, query_params={"sort": "model"}
    )
    request.app = app
    request.url_for = (
        lambda route,
        /,
        **params: f"/{route}/{params.get('name', params.get('path', ''))}"
    )
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
    assert '<table class="ledger" data-view="table">' in text
    assert 'data-view="cards"' in text
    assert "/static/view-toggle.js" in text
    assert "/static/row-link.js" in text
    assert "/static/row-link.js?v=" in text


def test_experiment_page_shows_design_grid_notes_and_runs(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    status, text = call(app, "/experiments/{name}", name="models-effort")

    assert status == 200
    assert collaborators["load_experiment"].await_args.args[:4] == (
        app.state.experiments,
        app.state.runs,
        "models-effort",
        {"sort": "model"},
    )
    assert '<span class="chip">haiku</span>' in text
    assert '<span class="chip quiet">true</span>' in text
    assert "<code>exit_code = 0</code>" in text
    assert "<h1>The plan</h1>" in text
    assert 'data-run-url="/run_block/models-effort"' in text
    assert 'data-restart-url="/restart_kernel/models-effort"' in text
    assert text.count('class="restart"') == 1
    assert "/static/run-cell.js" in text
    assert '<td class="cell done"' in text
    assert '<td class="cell"' in text
    assert "<pre>" + "x" * 100 + "</pre>" in text
    assert '<span class="status good"' in text
    assert 'aria-sort="descending"' in text
    assert '<span class="arrow">↓</span>' in text
    assert 'href="?sort=run_id#runs"' in text
    assert '<input type="hidden" name="sort" value="model">' in text
    assert '<input type="hidden" name="order" value="desc">' in text
    assert 'name="f.model" value="op"' in text
    assert "1 of 4" in text
    assert 'href="?sort=model&amp;order=desc#runs">Clear filters' in text


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


def test_builds_without_deprecation_warnings(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        create_app(Path("exp"), Path("data"), 30)


def test_stops_watching_on_shutdown(collaborators: dict[str, mock.MagicMock]) -> None:
    cancelled: list[object] = []

    async def watch_forever(db: object) -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(db)
            raise

    collaborators["drain_watch"].side_effect = watch_forever
    app = create_app(Path("exp"), Path("data"), 30)

    async def run_lifespan() -> list[object]:
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        return list(cancelled)

    assert asyncio.run(run_lifespan()) == [app.state.experiments, app.state.runs]


NOTE = "# Plan\n\n```python\na = 1\n```\n\n```python\na + 1\n```\n"


def post_run(
    app: Any,
    body: object,
    content_type: str = "application/json",
    action: str = "run",
    **params: str,
) -> Any:
    [endpoint] = [
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None)
        == f"/experiments/{{name}}/notes/{{note}}/{action}"
    ]
    request = mock.Mock(
        path_params={"name": "models-effort", "note": "PLAN.md", **params},
        headers={"content-type": content_type},
    )
    request.app = app
    request.json = mock.AsyncMock(return_value=body)
    return asyncio.run(endpoint(request))


@pytest.fixture
def kernel_class() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.create_app.NotebookKernel") as cls:
        cls.return_value.run = mock.AsyncMock(return_value="<pre>2</pre>")
        cls.return_value.stop = mock.AsyncMock()
        cls.return_value.outputs = {}
        yield cls


def test_run_executes_one_block_in_a_kernel_in_the_data_folder(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])

    response = post_run(app, {"block": 1})

    assert response.body == b"<pre>2</pre>"
    kernel_class.assert_called_once_with(Path("data"))
    kernel_class.return_value.run.assert_awaited_once_with("a + 1\n")
    sql = app.state.experiments.query.await_args.args[0]
    assert "experiment = 'models-effort' AND name = 'PLAN.md'" in sql


def test_run_reuses_the_note_kernel(app: Any, kernel_class: mock.MagicMock) -> None:
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])

    post_run(app, {"block": 0})
    post_run(app, {"block": 1})

    kernel_class.assert_called_once()


@pytest.mark.parametrize(
    "body", [{"block": 2}, {"block": 3}, {"block": -1}, {"block": "0"}, {}]
)
def test_run_rejects_a_missing_block(
    app: Any, kernel_class: mock.MagicMock, body: object
) -> None:
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])

    with pytest.raises(Exception) as raised:
        post_run(app, body)
    assert getattr(raised.value, "status_code", None) == 400
    kernel_class.assert_not_called()


def test_run_rejects_an_unknown_note(app: Any, kernel_class: mock.MagicMock) -> None:
    app.state.experiments.query = mock.AsyncMock(return_value=[])

    with pytest.raises(Exception) as raised:
        post_run(app, {"block": 0})
    assert getattr(raised.value, "status_code", None) == 404


@pytest.mark.parametrize("content_type", ["text/plain", "application/graphql"])
def test_run_requires_json_so_forms_on_other_sites_cannot_post(
    app: Any, kernel_class: mock.MagicMock, content_type: str
) -> None:
    with pytest.raises(Exception) as raised:
        post_run(app, {"block": 0}, content_type=content_type)
    assert getattr(raised.value, "status_code", None) == 415


def test_experiment_page_shows_outputs_of_blocks_already_run(
    app: Any, collaborators: dict[str, mock.MagicMock], kernel_class: mock.MagicMock
) -> None:
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])
    post_run(app, {"block": 0})
    call(app, "/experiments/{name}", name="models-effort")

    outputs_for = collaborators["load_experiment"].await_args.args[4]
    with mock.patch(
        "labnotes.create_app.saved_outputs", return_value=["<pre>1</pre>"]
    ) as saved:
        assert outputs_for("PLAN.md", NOTE) == ["<pre>1</pre>"]
        assert outputs_for("OTHER.md", "x") == ["<pre>1</pre>"]
    assert saved.call_args_list[0].args == (kernel_class.return_value, NOTE)
    assert saved.call_args_list[1].args == (None, "x")


def test_stops_kernels_on_shutdown(
    collaborators: dict[str, mock.MagicMock], kernel_class: mock.MagicMock
) -> None:
    app = create_app(Path("exp"), Path("data"), 30)

    async def lifecycle() -> None:
        async with app.router.lifespan_context(app):
            app.state.experiments.query = mock.AsyncMock(
                return_value=[{"content": NOTE}]
            )
            [endpoint] = [
                getattr(route, "endpoint")
                for route in app.routes
                if getattr(route, "path", "").endswith("/run")
            ]
            request = mock.Mock(
                path_params={"name": "e", "note": "n.md"},
                headers={"content-type": "application/json"},
            )
            request.app = app
            request.json = mock.AsyncMock(return_value={"block": 0})
            await endpoint(request)

    asyncio.run(lifecycle())

    kernel_class.return_value.stop.assert_awaited_once()


def test_stops_idle_kernels_in_the_background(
    collaborators: dict[str, mock.MagicMock], kernel_class: mock.MagicMock
) -> None:
    app = create_app(Path("exp"), Path("data"), 7)

    async def lifecycle() -> None:
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)

    asyncio.run(lifecycle())
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])
    post_run(app, {"block": 0})

    kernels, idle_minutes = collaborators["stop_idle_kernels"].await_args.args
    assert idle_minutes == 7
    assert kernels == {("models-effort", "PLAN.md"): kernel_class.return_value}


def test_restart_stops_the_note_kernel_and_keeps_it(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    kernel_class.return_value.restart = mock.AsyncMock()
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])
    post_run(app, {"block": 0})

    response = post_run(app, {}, action="restart")

    assert response.status_code == 204
    kernel_class.return_value.restart.assert_awaited_once_with()
    post_run(app, {"block": 1})
    kernel_class.assert_called_once()


def test_restart_before_any_run_starts_nothing(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])

    response = post_run(app, {}, action="restart")

    assert response.status_code == 204
    kernel_class.assert_not_called()


def test_restart_only_touches_its_own_note(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    kernel_class.return_value.restart = mock.AsyncMock()
    app.state.experiments.query = mock.AsyncMock(return_value=[{"content": NOTE}])
    post_run(app, {"block": 0})

    post_run(app, {}, action="restart", note="OTHER.md")

    kernel_class.return_value.restart.assert_not_awaited()


def test_restart_rejects_an_unknown_note(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    app.state.experiments.query = mock.AsyncMock(return_value=[])

    with pytest.raises(Exception) as raised:
        post_run(app, {}, action="restart")
    assert getattr(raised.value, "status_code", None) == 404


def test_restart_requires_json(app: Any, kernel_class: mock.MagicMock) -> None:
    with pytest.raises(Exception) as raised:
        post_run(app, {}, content_type="text/plain", action="restart")
    assert getattr(raised.value, "status_code", None) == 415
