import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.daemon.daemon_app import daemon_app

CONFIG = mock.Mock(name="config")
CURRENT = mock.Mock(name="current config")
EXPERIMENT = mock.Mock(name="experiment")


class Session:
    """Stands in for run_experiment: hands out controls, reports, then ends on cue."""

    def __init__(self) -> None:
        self.controls = mock.Mock()
        self.report: Callable[[dict[str, object]], None] = lambda event: None
        self.end: asyncio.Event | None = None
        self.error: Exception | None = None
        self.listen = True
        self.listen_now: Callable[[], None] = lambda: None

    async def __call__(
        self,
        config: object,
        name: str,
        experiment: object,
        concurrency: int,
        report: Callable[[dict[str, object]], None],
        listen: Callable[[object], None],
        timeout: float | None,
        only: dict[str, str] | None = None,
        args: list[str] | None = None,
        environment: dict[str, str] | None = None,
    ) -> list[object]:
        self.report = report
        self.end = asyncio.Event()
        self.listen_now = lambda: listen(self.controls)
        if self.listen:
            self.listen_now()
        report({"event": "planned", "folder": Path("/runs/r1")})
        await self.end.wait()
        if self.error is not None:
            raise self.error
        return []


@pytest.fixture
def collaborators() -> Iterator[dict[str, Any]]:
    session = Session()
    with (
        mock.patch(
            "labnotes.daemon.daemon_app.prepare_experiment",
            new=mock.AsyncMock(return_value=(EXPERIMENT, 3)),
        ) as prepare_experiment,
        mock.patch(
            "labnotes.daemon.daemon_app.run_experiment", side_effect=session.__call__
        ) as run_experiment,
        mock.patch(
            "labnotes.daemon.daemon_app.read_config", return_value=CURRENT
        ) as read_config,
        mock.patch("labnotes.daemon.daemon_app.GRACE_SECONDS", 0),
    ):
        yield {
            "session": session,
            "read_config": read_config,
            "prepare_experiment": prepare_experiment,
            "run_experiment": run_experiment,
        }


def call(
    app: Any,
    path: str,
    body: object = None,
    query: dict[str, str] | None = None,
    **params: str,
) -> Any:
    [endpoint] = [route.endpoint for route in app.routes if route.path == path]
    request = mock.Mock(
        path_params=params,
        query_params=query or {},
        json=mock.AsyncMock(return_value=body),
    )
    return endpoint(request)


def payload(response: Any) -> Any:
    return json.loads(response.body)


async def start(app: Any, name: str = "exp", **body: object) -> Any:
    return await call(
        app,
        "/experiments/{name}/run",
        {"experiment_config": None, "concurrency": None, **body},
        name=name,
    )


async def connect(app: Any, client: int = 1) -> AsyncIterator[str]:
    stream: AsyncIterator[str] = (await call(app, "/events")).body_iterator
    assert await next_event(stream) == {"event": "connected", "client": client}
    return stream


async def next_event(stream: AsyncIterator[str]) -> object:
    chunk = await asyncio.wait_for(anext(stream), 1)
    assert chunk.startswith("data: ")
    assert chunk.endswith("\n\n")
    return json.loads(chunk[6:])


def test_starts_a_session_and_streams_its_events(
    collaborators: dict[str, Any],
) -> None:
    session: Session = collaborators["session"]

    async def go() -> None:
        app = daemon_app(CONFIG)
        stream = await connect(app)

        response = await start(
            app,
            experiment_config="/x.toml",
            concurrency=2,
            timeout=90,
            only={"model": "small"},
            args=["--auth", "api"],
            setup="up",
            teardown="down",
            environment={"CALLER": "yes"},
        )

        assert response.status_code == 202
        collaborators["read_config"].assert_called_once_with(CONFIG.path)
        collaborators["prepare_experiment"].assert_awaited_once_with(
            CURRENT,
            "exp",
            Path("/x.toml"),
            2,
            {"model": "small"},
            ["--auth", "api"],
            "up",
            "down",
        )
        args = collaborators["run_experiment"].call_args.args
        assert args[:4] == (CURRENT, "exp", EXPERIMENT, 3)
        assert args[6] == 90
        assert collaborators["run_experiment"].call_args.kwargs == {
            "only": {"model": "small"},
            "args": ["--auth", "api"],
            "environment": {"CALLER": "yes"},
        }
        assert await next_event(stream) == {
            "event": "planned",
            "folder": "/runs/r1",
            "experiment": "exp",
        }
        assert not app.state.idle()
        assert session.end is not None
        session.end.set()
        assert await next_event(stream) == {
            "event": "done",
            "experiment": "exp",
            "error": None,
        }
        await stream.aclose()  # type: ignore[attr-defined]
        assert app.state.idle()

    asyncio.run(go())


def test_reads_the_default_experiment_config(
    collaborators: dict[str, Any],
) -> None:
    async def go() -> None:
        app = daemon_app(CONFIG)
        await start(app)
        collaborators["prepare_experiment"].assert_awaited_once_with(
            CURRENT, "exp", None, None, None, None, None, None
        )
        assert collaborators["run_experiment"].call_args.args[6] is None
        assert collaborators["run_experiment"].call_args.kwargs == {
            "only": None,
            "args": None,
            "environment": None,
        }

    asyncio.run(go())


def test_refuses_a_run_when_the_project_config_is_broken(
    collaborators: dict[str, Any],
) -> None:
    collaborators["read_config"].side_effect = ValueError("bad toml")

    async def go() -> None:
        app = daemon_app(CONFIG)
        response = await start(app)
        assert response.status_code == 400
        assert payload(response) == {"error": "bad toml"}
        collaborators["prepare_experiment"].assert_not_awaited()
        assert app.state.idle()

    asyncio.run(go())


def test_is_idle_with_no_clients_and_no_sessions(
    collaborators: dict[str, Any],
) -> None:
    async def go() -> None:
        app = daemon_app(CONFIG)
        assert app.state.idle()
        stream = await connect(app)
        assert not app.state.idle()
        await stream.aclose()  # type: ignore[attr-defined]
        assert app.state.idle()
        await start(app)
        assert not app.state.idle()

    asyncio.run(go())


def test_refuses_a_second_session_of_the_same_experiment(
    collaborators: dict[str, Any],
) -> None:
    async def go() -> None:
        app = daemon_app(CONFIG)
        await start(app)
        response = await start(app)
        assert response.status_code == 409
        assert payload(response) == {"error": "exp is already running."}
        assert (await start(app, "other")).status_code == 202

    asyncio.run(go())


def test_reports_an_experiment_that_cannot_be_read(
    collaborators: dict[str, Any],
) -> None:
    collaborators["prepare_experiment"].side_effect = [ValueError("No toml"), None]

    async def go() -> None:
        app = daemon_app(CONFIG)
        response = await start(app)
        assert response.status_code == 400
        assert payload(response) == {"error": "No toml"}
        assert app.state.idle()

    asyncio.run(go())
    collaborators["run_experiment"].assert_not_called()


def test_reports_a_session_that_fails_before_it_starts(
    collaborators: dict[str, Any],
) -> None:
    session: Session = collaborators["session"]
    session.listen = False
    session.error = RuntimeError("boom")

    async def go() -> None:
        app = daemon_app(CONFIG)
        stream = await connect(app)
        starting = asyncio.create_task(start(app))
        await next_event(stream)
        assert session.end is not None
        session.end.set()
        response = await starting
        assert response.status_code == 500
        assert payload(response) == {"error": "boom"}
        assert await next_event(stream) == {
            "event": "done",
            "experiment": "exp",
            "error": "boom",
        }
        await stream.aclose()  # type: ignore[attr-defined]
        assert app.state.idle()

    asyncio.run(go())


def test_reports_a_session_that_fails_while_running(
    collaborators: dict[str, Any],
) -> None:
    session: Session = collaborators["session"]
    session.error = RuntimeError("boom")

    async def go() -> None:
        app = daemon_app(CONFIG)
        stream = await connect(app)
        await start(app)
        await next_event(stream)
        assert session.end is not None
        session.end.set()
        assert await next_event(stream) == {
            "event": "done",
            "experiment": "exp",
            "error": "boom",
        }

    asyncio.run(go())


def test_passes_controls_to_the_session(collaborators: dict[str, Any]) -> None:
    controls = collaborators["session"].controls

    async def go() -> None:
        app = daemon_app(CONFIG)
        await start(app)
        path = "/experiments/{name}/{action}"
        response = await call(app, path, {"args": ["r1"]}, name="exp", action="kill")
        assert response.status_code == 200
        controls.kill.assert_called_once_with("r1")
        await call(app, path, {"args": []}, name="exp", action="finish")
        controls.finish.assert_called_once_with()

    asyncio.run(go())


@pytest.mark.parametrize(("name", "action"), [("exp", "explode"), ("nope", "kill")])
def test_refuses_an_unknown_control(
    collaborators: dict[str, Any], name: str, action: str
) -> None:
    async def go() -> None:
        app = daemon_app(CONFIG)
        await start(app)
        response = await call(
            app,
            "/experiments/{name}/{action}",
            {"args": []},
            name=name,
            action=action,
        )
        assert response.status_code == 404
        assert payload(response) == {"error": f"No {action} for {name}."}

    asyncio.run(go())


def test_stop_interrupts_every_session_then_again_after_a_grace(
    collaborators: dict[str, Any],
) -> None:
    controls = collaborators["session"].controls

    async def go() -> None:
        app = daemon_app(CONFIG)
        await start(app)
        response = await call(app, "/stop")
        assert response.status_code == 200
        assert controls.interrupt.call_count == 1
        await asyncio.sleep(0.01)
        assert controls.interrupt.call_count == 2

    asyncio.run(go())


def test_stop_spares_sessions_started_after_it(
    collaborators: dict[str, Any],
) -> None:
    controls = collaborators["session"].controls

    async def go() -> None:
        app = daemon_app(CONFIG)
        app.state.stop()
        await start(app)
        await asyncio.sleep(0.01)
        controls.interrupt.assert_not_called()

    asyncio.run(go())


def test_numbers_each_client() -> None:
    async def go() -> None:
        app = daemon_app(CONFIG)
        await connect(app, 1)
        await connect(app, 2)

    asyncio.run(go())


def test_finishes_a_session_once_its_client_leaves(
    collaborators: dict[str, Any],
) -> None:
    controls = collaborators["session"].controls

    async def go() -> None:
        app = daemon_app(CONFIG)
        lower = await connect(app, 1)
        owner = await connect(app, 2)
        higher = await connect(app, 3)
        await start(app, "low", client=1)
        await start(app, "mine", client=2)
        await start(app, "high", client=3)
        await start(app, "anyone")
        await owner.aclose()  # type: ignore[attr-defined]
        assert controls.finish.call_count == 1
        await lower.aclose()  # type: ignore[attr-defined]
        await higher.aclose()  # type: ignore[attr-defined]
        assert controls.finish.call_count == 3
        controls.interrupt.assert_not_called()

    asyncio.run(go())


def test_matches_an_owner_by_value_past_the_cached_ints(
    collaborators: dict[str, Any],
) -> None:
    controls = collaborators["session"].controls

    async def go() -> None:
        with mock.patch("labnotes.daemon.daemon_app.itertools.count") as count:
            count.return_value = iter(range(1000, 1002))
            app = daemon_app(CONFIG)
        owner = await connect(app, 1000)
        await start(app, client=int("1000"))
        await owner.aclose()  # type: ignore[attr-defined]
        controls.finish.assert_called_once_with()

    asyncio.run(go())


def test_finishes_a_session_whose_client_left_before_it_started(
    collaborators: dict[str, Any],
) -> None:
    session: Session = collaborators["session"]
    controls = session.controls
    session.listen = False

    async def go() -> None:
        app = daemon_app(CONFIG)
        owner = await connect(app, 1)
        starting = asyncio.create_task(start(app, client=1))
        await next_event(owner)
        await owner.aclose()  # type: ignore[attr-defined]
        controls.finish.assert_not_called()
        session.listen_now()
        assert (await starting).status_code == 202
        controls.finish.assert_called_once_with()

    asyncio.run(go())


def test_forgets_the_owner_of_an_ended_session(
    collaborators: dict[str, Any],
) -> None:
    session: Session = collaborators["session"]
    controls = session.controls

    async def go() -> None:
        app = daemon_app(CONFIG)
        owner = await connect(app, 1)
        await start(app, client=1)
        await next_event(owner)
        assert session.end is not None
        session.end.set()
        await next_event(owner)
        await start(app)
        await owner.aclose()  # type: ignore[attr-defined]
        controls.finish.assert_not_called()

    asyncio.run(go())


class Parsed(str):
    """A query value that is equal to, but not the same object as, a literal."""


async def watch(app: Any, client: int) -> AsyncIterator[str]:
    response = await call(app, "/events", query={"watch": Parsed("1")})
    stream: AsyncIterator[str] = response.body_iterator
    assert await next_event(stream) == {"event": "connected", "client": client}
    return stream


def test_replays_running_sessions_to_a_watcher(
    collaborators: dict[str, Any],
) -> None:
    session: Session = collaborators["session"]

    async def go() -> None:
        app = daemon_app(CONFIG)
        await start(app)
        session.report({"event": "idle"})
        watcher = await watch(app, 1)
        assert await next_event(watcher) == {
            "event": "planned",
            "folder": "/runs/r1",
            "experiment": "exp",
        }
        assert await next_event(watcher) == {"event": "idle", "experiment": "exp"}
        assert await next_event(watcher) == {"event": "replayed"}
        assert session.end is not None
        session.end.set()
        await next_event(watcher)
        assert await next_event(await watch(app, 2)) == {"event": "replayed"}

    asyncio.run(go())


def test_says_when_the_replay_is_over_with_nothing_running() -> None:
    async def go() -> None:
        app = daemon_app(CONFIG)
        assert await next_event(await watch(app, 1)) == {"event": "replayed"}

    asyncio.run(go())


def test_does_not_keep_the_daemon_up_for_watchers(
    collaborators: dict[str, Any],
) -> None:
    async def go() -> None:
        app = daemon_app(CONFIG)
        watcher = await watch(app, 1)
        assert app.state.idle()
        client = await connect(app, 2)
        assert not app.state.idle()
        await client.aclose()  # type: ignore[attr-defined]
        assert app.state.idle()
        await watcher.aclose()  # type: ignore[attr-defined]
        assert app.state.idle()

    asyncio.run(go())


def test_does_not_replay_to_a_plain_client(collaborators: dict[str, Any]) -> None:
    session: Session = collaborators["session"]

    async def go() -> None:
        app = daemon_app(CONFIG)
        await start(app)
        client = await connect(app, 1)
        session.report({"event": "idle"})
        assert await next_event(client) == {"event": "idle", "experiment": "exp"}

    asyncio.run(go())
