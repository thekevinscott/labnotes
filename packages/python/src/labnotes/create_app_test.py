import asyncio
import json
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.create_app import create_app

CONFIG = mock.Mock(root=Path("/p/project"), mode="matrix")


EXPERIMENT: dict[str, object] = {"name": "models-effort"}


NOTE = "# Plan\n\n```python\na = 1\n```\n\n```python\na + 1\n```\n"


def test_formats_durations_in_templates() -> None:
    module = create_app.__globals__
    assert module["templates"].env.filters["duration"] is module["format_duration"]


def test_formats_start_times_in_templates() -> None:
    module = create_app.__globals__
    assert module["templates"].env.filters["started"] is module["format_started"]


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.create_app.open_tables") as open_tables,
        mock.patch(
            "labnotes.create_app.experiment_notes",
            new_callable=mock.AsyncMock,
            return_value=[
                {
                    "name": "PLAN.md",
                    "path": "/p/project/e/files/PLAN.md",
                    "content": NOTE,
                }
            ],
        ) as experiment_notes,
        mock.patch("labnotes.create_app.note_path") as note_path,
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
        mock.patch("labnotes.create_app.templates") as templates,
    ):
        templates.TemplateResponse.return_value = mock.Mock(status_code=200, body=b"")
        open_tables.return_value.ready = mock.AsyncMock()
        yield {
            "open_tables": open_tables,
            "experiment_notes": experiment_notes,
            "note_path": note_path,
            "drain_watch": drain,
            "list_experiments": list_experiments,
            "load_experiment": load_experiment,
            "templates": templates,
        }


@pytest.fixture
def app(collaborators: dict[str, mock.MagicMock]) -> Iterator[Any]:
    app = create_app(CONFIG)

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
    response = asyncio.run(endpoint(request))
    return response.status_code, response.body.decode()


def test_opens_the_tables_and_watches_them(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    tables = collaborators["open_tables"].return_value
    collaborators["open_tables"].assert_called_once_with(CONFIG)
    tables.ready.assert_awaited_once()
    watched = [call.args[0] for call in collaborators["drain_watch"].await_args_list]
    assert watched == [tables]


def test_index_lists_experiments(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    status, _ = call(app, "/")

    assert status == 200
    collaborators["list_experiments"].assert_awaited_once_with(
        app.state.tables, "matrix"
    )
    collaborators["templates"].TemplateResponse.assert_called_once_with(
        mock.ANY, "index.html", {"experiments": [EXPERIMENT], "folder": "project"}
    )


def test_experiment_page_loads_the_named_experiment(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    status, _ = call(app, "/experiments/{name}", name="models-effort")

    assert status == 200
    assert collaborators["load_experiment"].await_args.args[:5] == (
        app.state.tables,
        Path("/p/project"),
        "matrix",
        "models-effort",
        {"sort": "model"},
    )
    collaborators["templates"].TemplateResponse.assert_called_once_with(
        mock.ANY, "experiment.html", {"experiment": EXPERIMENT}
    )


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
        create_app(CONFIG)


def test_stops_watching_on_shutdown(collaborators: dict[str, mock.MagicMock]) -> None:
    cancelled: list[object] = []

    async def watch_forever(db: object) -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(db)
            raise

    collaborators["drain_watch"].side_effect = watch_forever
    app = create_app(CONFIG)

    async def run_lifespan() -> list[object]:
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        return list(cancelled)

    assert asyncio.run(run_lifespan()) == [app.state.tables]


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
        == f"/experiments/{{name}}/notes/{{note:path}}/{action}"
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


def test_run_executes_one_block_in_a_kernel_at_the_root(
    app: Any, collaborators: dict[str, mock.MagicMock], kernel_class: mock.MagicMock
) -> None:
    response = post_run(app, {"block": 1})

    assert response.body == b"<pre>2</pre>"
    kernel_class.assert_called_once_with(Path("/p/project"))
    kernel_class.return_value.run.assert_awaited_once_with("a + 1\n")
    collaborators["experiment_notes"].assert_awaited_with(
        app.state.tables, Path("/p/project"), "models-effort", "PLAN.md"
    )


def test_run_reuses_the_note_kernel(app: Any, kernel_class: mock.MagicMock) -> None:
    post_run(app, {"block": 0})
    post_run(app, {"block": 1})

    kernel_class.assert_called_once()


@pytest.mark.parametrize(
    "body", [{"block": 2}, {"block": 3}, {"block": -1}, {"block": "0"}, {}]
)
def test_run_rejects_a_missing_block(
    app: Any, kernel_class: mock.MagicMock, body: object
) -> None:
    with pytest.raises(Exception) as raised:
        post_run(app, body)
    assert getattr(raised.value, "status_code", None) == 400
    kernel_class.assert_not_called()


def test_run_rejects_an_unknown_note(
    app: Any, collaborators: dict[str, mock.MagicMock], kernel_class: mock.MagicMock
) -> None:
    collaborators["experiment_notes"].return_value = []

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
    post_run(app, {"block": 0})
    call(app, "/experiments/{name}", name="models-effort")

    outputs_for = collaborators["load_experiment"].await_args.args[5]
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
    app = create_app(CONFIG)

    async def lifecycle() -> None:
        async with app.router.lifespan_context(app):
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


def test_restart_stops_the_note_kernel_and_keeps_it(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    kernel_class.return_value.restart = mock.AsyncMock()
    post_run(app, {"block": 0})

    response = post_run(app, {}, action="restart")

    assert response.status_code == 204
    kernel_class.return_value.restart.assert_awaited_once_with()
    post_run(app, {"block": 1})
    kernel_class.assert_called_once()


def test_restart_before_any_run_starts_nothing(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    response = post_run(app, {}, action="restart")

    assert response.status_code == 204
    kernel_class.assert_not_called()


def test_restart_only_touches_its_own_note(
    app: Any, kernel_class: mock.MagicMock
) -> None:
    kernel_class.return_value.restart = mock.AsyncMock()
    post_run(app, {"block": 0})

    post_run(app, {}, action="restart", note="OTHER.md")

    kernel_class.return_value.restart.assert_not_awaited()


def test_restart_rejects_an_unknown_note(
    app: Any, collaborators: dict[str, mock.MagicMock], kernel_class: mock.MagicMock
) -> None:
    collaborators["experiment_notes"].return_value = []

    with pytest.raises(Exception) as raised:
        post_run(app, {}, action="restart")
    assert getattr(raised.value, "status_code", None) == 404


def test_restart_requires_json(app: Any, kernel_class: mock.MagicMock) -> None:
    with pytest.raises(Exception) as raised:
        post_run(app, {}, content_type="text/plain", action="restart")
    assert getattr(raised.value, "status_code", None) == 415


def note_endpoint(app: Any, method: str) -> Any:
    [endpoint] = [
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/experiments/{name}/notes/{note:path}"
        and method in route.methods
    ]
    return endpoint


def put_note(app: Any, body: object, content_type: str = "application/json") -> Any:
    endpoint = note_endpoint(app, "PUT")
    request = mock.Mock(
        path_params={"name": "models-effort", "note": "PLAN.md"},
        headers={"content-type": content_type},
    )
    request.app = app
    request.json = mock.AsyncMock(return_value=body)
    return asyncio.run(endpoint(request))


def test_put_saves_the_note_over_its_base(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    with (
        mock.patch("labnotes.create_app.save_note", return_value=None) as save,
        mock.patch(
            "labnotes.create_app.wait_for_note", new_callable=mock.AsyncMock
        ) as wait,
    ):
        response = put_note(app, {"base": NOTE, "content": "new"})

    assert response.status_code == 204
    save.assert_called_once_with(collaborators["note_path"].return_value, NOTE, "new")
    collaborators["note_path"].assert_called_once_with(
        CONFIG, "models-effort", "PLAN.md"
    )
    wait.assert_awaited_once_with(
        app.state.tables, Path("/p/project"), "models-effort", "PLAN.md", "new"
    )


def test_put_refuses_a_stale_base_with_the_file_on_disk(app: Any) -> None:
    with mock.patch("labnotes.create_app.save_note", return_value="theirs"):
        response = put_note(app, {"base": "old", "content": "new"})

    assert response.status_code == 409
    assert json.loads(response.body) == {"content": "theirs"}


@pytest.mark.parametrize(
    "body",
    [
        {"content": "new"},
        {"base": NOTE},
        {"base": 1, "content": "new"},
        {"base": NOTE, "content": 1},
    ],
)
def test_put_rejects_a_body_without_base_and_content(app: Any, body: object) -> None:
    with mock.patch("labnotes.create_app.save_note") as save:
        with pytest.raises(Exception) as raised:
            put_note(app, body)
    assert getattr(raised.value, "status_code", None) == 400
    save.assert_not_called()


def test_put_rejects_an_unknown_note(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["note_path"].return_value = None

    with mock.patch("labnotes.create_app.save_note") as save:
        with pytest.raises(Exception) as raised:
            put_note(app, {"base": NOTE, "content": "new"})
    assert getattr(raised.value, "status_code", None) == 404
    save.assert_not_called()


@pytest.mark.parametrize("content_type", ["application/csv", "text/plain"])
def test_put_requires_json(app: Any, content_type: str) -> None:
    with pytest.raises(Exception) as raised:
        put_note(app, {"base": NOTE, "content": "new"}, content_type=content_type)
    assert getattr(raised.value, "status_code", None) == 415


def post_conflict(
    app: Any, body: object, content_type: str = "application/json"
) -> Any:
    [endpoint] = [
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None)
        == "/experiments/{name}/notes/{note:path}/conflict"
    ]
    request = mock.Mock(
        path_params={"name": "models-effort", "note": "PLAN.md"},
        headers={"content-type": content_type},
    )
    request.app = app
    request.json = mock.AsyncMock(return_value=body)
    return asyncio.run(endpoint(request))


def test_conflict_saves_a_copy_beside_the_note(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    copy = Path("/p/project/e/files/PLAN (Conflicted copy 202610200905).md")
    with (
        mock.patch("labnotes.create_app.save_conflict_copy", return_value=copy) as save,
        mock.patch("labnotes.create_app.datetime") as clock,
    ):
        response = post_conflict(app, {"content": "theirs"})

    assert response.status_code == 201
    assert json.loads(response.body) == {"name": copy.name}
    save.assert_called_once_with(
        collaborators["note_path"].return_value, "theirs", clock.now.return_value
    )
    collaborators["note_path"].assert_called_once_with(
        CONFIG, "models-effort", "PLAN.md"
    )


@pytest.mark.parametrize("body", [{}, {"content": 1}])
def test_conflict_rejects_a_body_without_content(app: Any, body: object) -> None:
    with mock.patch("labnotes.create_app.save_conflict_copy") as save:
        with pytest.raises(Exception) as raised:
            post_conflict(app, body)
    assert getattr(raised.value, "status_code", None) == 400
    save.assert_not_called()


def test_conflict_rejects_an_unknown_note(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["note_path"].return_value = None

    with pytest.raises(Exception) as raised:
        post_conflict(app, {"content": "theirs"})
    assert getattr(raised.value, "status_code", None) == 404


def test_conflict_requires_json(app: Any) -> None:
    with pytest.raises(Exception) as raised:
        post_conflict(app, {"content": "theirs"}, content_type="text/plain")
    assert getattr(raised.value, "status_code", None) == 415


def test_get_returns_the_note_markdown_without_requiring_json(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    request = mock.Mock(
        path_params={"name": "models-effort", "note": "PLAN.md"}, headers={}
    )
    request.app = app

    response = asyncio.run(note_endpoint(app, "GET")(request))

    assert response.body.decode() == NOTE
    assert response.media_type == "text/markdown"
    collaborators["experiment_notes"].assert_awaited_with(
        app.state.tables, Path("/p/project"), "models-effort", "PLAN.md"
    )


def test_get_rejects_an_unknown_note(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["experiment_notes"].return_value = []
    request = mock.Mock(path_params={"name": "e", "note": "nope.md"}, headers={})
    request.app = app

    with pytest.raises(Exception) as raised:
        asyncio.run(note_endpoint(app, "GET")(request))
    assert getattr(raised.value, "status_code", None) == 404


def test_streams_the_experiments_file_changes(app: Any) -> None:
    [endpoint] = [
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/experiments/{name}/changes"
    ]
    request = mock.Mock(path_params={"name": "models-effort"})
    request.app = app

    with mock.patch(
        "labnotes.create_app.file_changes", return_value=iter(["data: 1\n\n"])
    ) as changes:
        response = asyncio.run(endpoint(request))

    assert response.media_type == "text/event-stream"
    changes.assert_called_once_with(app.state.tables, "models-effort")


RUN: dict[str, object] = {"id": "g1/r1"}


def test_run_page_loads_the_named_run(
    app: Any, collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch(
        "labnotes.create_app.load_run", new_callable=mock.AsyncMock, return_value=RUN
    ) as load_run:
        status, _ = call(
            app, "/experiments/{name}/runs/{run:path}", name="alpha", run="g1/r1"
        )

    assert status == 200
    load_run.assert_awaited_once_with(app.state.tables, "alpha", "g1/r1")
    collaborators["templates"].TemplateResponse.assert_called_once_with(
        mock.ANY, "run.html", {"run": RUN}
    )


@pytest.mark.parametrize(
    "path",
    ["/experiments/{name}/runs/{run:path}", "/experiments/{name}/output/{run:path}"],
)
def test_unknown_run_is_not_found(app: Any, path: str) -> None:
    with (
        mock.patch(
            "labnotes.create_app.load_run",
            new_callable=mock.AsyncMock,
            return_value=None,
        ),
        mock.patch("labnotes.create_app.run_output") as output,
        pytest.raises(Exception) as raised,
    ):
        call(app, path, name="alpha", run="nope")
    assert getattr(raised.value, "status_code", None) == 404
    output.assert_not_called()


def test_streams_the_runs_output(app: Any) -> None:
    [endpoint] = [
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/experiments/{name}/output/{run:path}"
    ]
    request = mock.Mock(path_params={"name": "alpha", "run": "g1/r1"})
    request.app = app

    with (
        mock.patch(
            "labnotes.create_app.load_run",
            new_callable=mock.AsyncMock,
            return_value=RUN,
        ),
        mock.patch(
            "labnotes.create_app.run_output", return_value=iter(["data: 1\n\n"])
        ) as output,
    ):
        response = asyncio.run(endpoint(request))

    assert response.media_type == "text/event-stream"
    output.assert_called_once_with(
        app.state.tables, Path("/p/project"), "alpha", "g1/r1"
    )


def post_note(app: Any, content_type: str = "application/json") -> Any:
    [endpoint] = [
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/experiments/{name}/notes"
    ]
    request = mock.Mock(
        path_params={"name": "models effort"}, headers={"content-type": content_type}
    )
    request.app = app
    return asyncio.run(endpoint(request)), request


def test_post_creates_a_note_and_renders_it_for_the_page(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    app = create_app(CONFIG)
    note = tmp_path / "Untitled 2.md"
    note.write_text("# Untitled\n\n```python\n1\n```\n", encoding="utf-8")
    with (
        mock.patch("labnotes.create_app.create_note", return_value=note) as create,
        mock.patch(
            "labnotes.create_app.render_markdown", return_value="<h1>Untitled</h1>"
        ) as render,
    ):
        _, request = post_note(app)

    create.assert_called_once_with(CONFIG, "models effort")
    templates = collaborators["templates"]
    templates.TemplateResponse.assert_called_once_with(
        request,
        "note.html",
        {
            "e": {"name": "models effort"},
            "note": {
                "name": "Untitled 2.md",
                "content": "# Untitled\n\n```python\n1\n```\n",
                "html": "<h1>Untitled</h1>",
                "runnable": True,
            },
        },
        status_code=201,
    )
    render.assert_called_once_with("# Untitled\n\n```python\n1\n```\n", ())


def test_post_marks_a_note_without_python_as_not_runnable(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    app = create_app(CONFIG)
    note = tmp_path / "Untitled.md"
    note.write_text("# Untitled\n", encoding="utf-8")
    with (
        mock.patch("labnotes.create_app.create_note", return_value=note),
        mock.patch("labnotes.create_app.render_markdown"),
    ):
        post_note(app)

    context = collaborators["templates"].TemplateResponse.call_args.args[2]
    assert context["note"]["runnable"] is False


def test_post_rejects_an_unknown_experiment(app: Any) -> None:
    with (
        mock.patch("labnotes.create_app.create_note", return_value=None),
        pytest.raises(Exception) as raised,
    ):
        post_note(app)
    assert getattr(raised.value, "status_code", None) == 404


@pytest.mark.parametrize("content_type", ["application/csv", "text/plain"])
def test_post_requires_json(app: Any, content_type: str) -> None:
    with (
        mock.patch("labnotes.create_app.create_note") as create,
        pytest.raises(Exception) as raised,
    ):
        post_note(app, content_type)
    assert getattr(raised.value, "status_code", None) == 415
    create.assert_not_called()
