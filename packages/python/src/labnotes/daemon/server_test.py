import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.daemon.server import (
    ExperimentDaemon,
    Invocation,
    Queued,
    serve_daemon,
)


INVALID = {"ok": False, "error": "Invalid request"}


def config(root: Path) -> mock.Mock:
    return mock.Mock(
        root=root,
        experiments="{experiment}",
        runs="{experiment}/runs/{run}",
    )


@pytest.fixture
def paths(tmp_path: Path) -> Iterator[tuple[Path, Path, Path]]:
    lock = tmp_path / "daemon.lock"
    socket = tmp_path / "daemon.sock"
    record = tmp_path / "socket.record"
    with (
        mock.patch("labnotes.daemon.server.lock_path", return_value=lock),
        mock.patch("labnotes.daemon.server.socket_path", return_value=socket),
        mock.patch("labnotes.daemon.server.socket_record", return_value=record),
    ):
        yield lock, socket, record


def test_commands_control_one_invocation_and_reply_to_bad_requests(
    tmp_path: Path,
) -> None:
    async def drive() -> None:
        project = config(tmp_path)
        daemon = ExperimentDaemon(project, "exp")
        done = asyncio.Event()
        set_concurrency = mock.Mock()
        kill = mock.Mock()
        finish = mock.Mock()
        controls = mock.Mock(
            interrupt=done.set,
            finish_up=mock.Mock(),
            set_concurrency=set_concurrency,
            kill=kill,
            finish=finish,
        )
        selected = mock.Mock(batch="one")

        async def run(report, listen):
            listen(controls)
            await done.wait()
            return []

        selected.side_effect = run
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            assert await daemon.dispatch({"command": "start", "options": []}) == {
                "ok": False,
                "error": "options must be an object",
            }
            assert await daemon.dispatch({"command": "restart"}) == {
                "ok": False,
                "error": "restart needs run_id",
            }
            assert await daemon.dispatch({"command": "start"}) == {
                "ok": True,
                "batch": "one",
            }
            assert await daemon.dispatch({"command": "stop_one"}) == {
                "ok": False,
                "error": "stop_one needs a run id",
            }
            assert await daemon.dispatch({"command": "stop_one", "run": "r"}) == {
                "ok": True
            }
            kill.assert_called_once_with("r")
            assert (await daemon.dispatch({"command": "set_concurrency", "count": 0}))[
                "ok"
            ] is False
            assert (
                await daemon.dispatch(
                    {"command": "set_concurrency", "count": 2, "batch": "missing"}
                )
            )["ok"] is False
            assert await daemon.dispatch(
                {
                    "command": "set_concurrency",
                    "count": 2,
                    "batch": "one",
                }
            ) == {"ok": True}
            assert await daemon.dispatch(
                {"command": "set_concurrency", "count": 3}
            ) == {"ok": True}
            assert set_concurrency.call_args_list == [
                mock.call(2),
                mock.call(3),
            ]
            assert await daemon.dispatch({"command": "batches"}) == {
                "ok": True,
                "batches": ["one"],
            }
            assert await daemon.dispatch({"command": "finish_up"}) == {"ok": True}
            controls.finish_up.assert_called_once_with()
            assert (await daemon.dispatch({"command": "unknown"}))["ok"] is False
            assert await daemon.dispatch({"command": "stop_all"}) == {"ok": True}
            await asyncio.sleep(0)
            assert not daemon.active
            finish.assert_called_once_with()

    asyncio.run(drive())


def test_finished_up_batch_releases_planned_runs_from_reservations(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = [
        {"event": "planned", "runs": [{"run": "r1", "params": {"m": "a"}}]},
        {"event": "finishing up"},
    ]

    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        daemon.active["finished_up"] = Invocation(events=events)
        selected = mock.Mock(batch="new")

        async def fail_early(report, listen):
            raise ValueError("stop here")

        selected.side_effect = fail_early
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ) as start:
            await daemon.start({})
        assert start.call_args.args[14] == {}

    asyncio.run(drive())


def test_finish_up_command_decoded_from_socket_json_reaches_controls(
    tmp_path: Path,
) -> None:
    daemon = ExperimentDaemon(config(tmp_path), "exp")
    controls = mock.Mock()
    daemon.active["active"] = Invocation(controls=controls)

    reply = asyncio.run(daemon.dispatch(json.loads('{"command": "finish_up"}')))

    assert reply == {"ok": True}
    controls.finish_up.assert_called_once_with()


def test_finish_up_requested_during_preparation_reaches_new_controls(
    tmp_path: Path,
) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        preparing = asyncio.Event()
        ready = asyncio.Event()
        done = asyncio.Event()
        controls = mock.Mock(finish_up=mock.Mock(side_effect=done.set))
        selected = mock.Mock(batch="new")

        async def run(report, listen):
            preparing.set()
            await ready.wait()
            listen(controls)
            await done.wait()
            return []

        selected.side_effect = run
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            starting = asyncio.create_task(daemon.start({}))
            await preparing.wait()
            assert await daemon.dispatch({"command": "finish_up"}) == {"ok": True}
            ready.set()
            assert (await starting)["ok"] is True
            await asyncio.sleep(0)
        controls.finish_up.assert_called_once_with()
        controls.interrupt.assert_not_called()

    asyncio.run(drive())


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, (None, None, False)),
        (
            {"retries": 2, "retry_wait": 1.5, "replace_capped": True},
            (2, 1.5, True),
        ),
    ],
)
def test_start_passes_retries_retry_wait_and_replace_capped(
    tmp_path: Path, options: dict[str, object], expected: tuple[object, ...]
) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(batch="one")

        async def fail_early(report, listen):
            raise ValueError("stop here")

        selected.side_effect = fail_early
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ) as start:
            await daemon.start(options)
        assert start.call_args.args[11:14] == expected
        assert start.call_args.args[14:16] == ({}, None)

    asyncio.run(drive())


def test_start_returns_preparation_error_and_records_late_error(
    tmp_path: Path,
) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(batch="bad")

        async def fail_early(report, listen):
            raise ValueError("bad experiment")

        selected.side_effect = fail_early
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            assert await daemon.start({}) == {"ok": False, "error": "bad experiment"}
        await asyncio.sleep(0)
        assert not daemon.active

        async def fail_late(report, listen):
            listen(mock.Mock())
            await asyncio.sleep(0)
            raise RuntimeError("run failed")

        selected.side_effect = fail_late
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            assert (await daemon.start({}))["ok"] is True
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert daemon.history["bad"].events == [
            {"event": "daemon error", "error": "run failed", "at": mock.ANY}
        ]
        assert not daemon.active

    asyncio.run(drive())


def test_start_waits_for_slow_preparation_without_a_deadline(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(batch="slow")

        async def run(report, listen):
            await asyncio.sleep(0.2)
            listen(mock.Mock())
            return []

        selected.side_effect = run
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            assert await daemon.start({}) == {
                "ok": True,
                "batch": "slow",
            }

    asyncio.run(drive())


def test_start_that_ends_before_any_run_reports_it(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(batch="none")

        async def run(report, listen):
            return []

        selected.side_effect = run
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            assert await daemon.start({}) == {
                "ok": False,
                "error": "Start ended before any run",
            }
        assert not daemon.active

    asyncio.run(drive())


def test_start_passes_progress_and_reports_a_queued_start(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(batch="one")

        async def run(report, listen):
            listen(mock.Mock())
            return []

        selected.side_effect = run
        steps: list[str] = []
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ) as start:
            async with daemon.start_lock:
                waiting = asyncio.create_task(
                    daemon.dispatch({"command": "start", "options": {}}, steps.append)
                )
                await asyncio.sleep(0)
            assert (await waiting)["ok"] is True
        assert steps == ["Waiting for an earlier start"]
        assert start.call_args.args[-1] == steps.append

    asyncio.run(drive())


def test_repeated_listen_callback_does_not_reply_twice(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(batch="one")

        async def run(report, listen):
            controls = mock.Mock()
            listen(controls)
            listen(controls)
            return []

        selected.side_effect = run
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            assert (await daemon.start({}))["ok"] is True

    asyncio.run(drive())


def test_stop_requested_while_start_is_preparing_reaches_controls(
    tmp_path: Path,
) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        preparing = asyncio.Event()
        release = asyncio.Event()
        interrupted = mock.Mock()
        selected = mock.Mock(batch="pending")

        async def run(report, listen):
            preparing.set()
            await release.wait()
            listen(mock.Mock(interrupt=interrupted))
            return []

        selected.side_effect = run
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            started = asyncio.create_task(daemon.start({}))
            await preparing.wait()
            daemon.stop_all()
            release.set()
            assert (await started)["ok"] is True
        interrupted.assert_called_once_with()

    asyncio.run(drive())


def test_commands_ignore_invocation_still_preparing(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        pending = Invocation()
        daemon.active["pending"] = pending
        daemon.stop_all()
        assert pending.stop_requested is True
        assert await daemon.dispatch({"command": "stop_one", "run": "r"}) == {
            "ok": True
        }
        assert await daemon.dispatch({"command": "set_concurrency", "count": 2}) == {
            "ok": True
        }

    asyncio.run(drive())


def test_attached_client_prevents_idle_exit(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        daemon.clients = 1
        with mock.patch("labnotes.daemon.server.IDLE_SECONDS", 0):
            waiting = asyncio.create_task(daemon.wait_until_idle())
            await asyncio.sleep(0.02)
            assert not waiting.done()
            daemon.clients = 0
            await asyncio.wait_for(waiting, timeout=1)

    asyncio.run(drive())


def test_shutdown_exits_even_with_an_attached_client(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        daemon.clients = 1
        daemon.closing = True
        await asyncio.wait_for(daemon.wait_until_idle(), timeout=0.1)

    asyncio.run(drive())


def test_server_exits_after_idle_and_second_owner_does_not_bind(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    async def drive() -> None:
        project = config(tmp_path)
        _, _, record = paths
        with (
            mock.patch(
                "labnotes.daemon.server.fcntl.flock", side_effect=BlockingIOError
            ),
            mock.patch(
                "labnotes.daemon.server.asyncio.sleep", new=mock.AsyncMock()
            ) as sleep,
        ):
            await serve_daemon(project, "exp")
            assert not record.exists()
            assert sleep.await_count == 10
        with (
            mock.patch("labnotes.daemon.server.fcntl.flock"),
            mock.patch("labnotes.daemon.server.IDLE_SECONDS", 0.05),
        ):
            await serve_daemon(project, "exp")
        assert not record.exists()

    asyncio.run(drive())


def test_server_retries_a_probe_lock_before_binding(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    async def drive() -> None:
        project = config(tmp_path)
        _, _, record = paths
        with (
            mock.patch(
                "labnotes.daemon.server.fcntl.flock",
                side_effect=[BlockingIOError, None],
            ) as flock,
            mock.patch(
                "labnotes.daemon.server.asyncio.sleep", new=mock.AsyncMock()
            ) as sleep,
            mock.patch("labnotes.daemon.server.IDLE_SECONDS", 0),
        ):
            await serve_daemon(project, "exp")
        assert flock.call_count == 2
        assert sleep.await_args_list[0] == mock.call(0.1)
        assert not record.exists()

    asyncio.run(drive())


def test_server_accepts_connections_before_its_http_server_starts(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    accepted: list[bool] = []

    async def startup(sockets: list[object]) -> None:
        _, path, _ = paths
        _, writer = await asyncio.open_unix_connection(str(path))
        writer.close()
        accepted.append(True)

    async def drive() -> None:
        with (
            mock.patch("labnotes.daemon.server.fcntl.flock"),
            mock.patch("labnotes.daemon.server.IDLE_SECONDS", 0),
            mock.patch("uvicorn.Server") as server,
            mock.patch("uvicorn.Config") as settings,
        ):
            server.return_value.startup = mock.AsyncMock(side_effect=startup)
            server.return_value.shutdown = mock.AsyncMock()
            await serve_daemon(config(tmp_path), "exp")
        [(app,)] = [call.args for call in settings.call_args_list]
        assert isinstance(app, ExperimentDaemon)
        settings.assert_called_once_with(
            app,
            lifespan="off",
            log_config=None,
            access_log=False,
            timeout_graceful_shutdown=1,
        )
        server.assert_called_once_with(settings.return_value)

    asyncio.run(drive())
    assert accepted == [True]


def test_server_signal_stops_and_closes_early(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    async def drive() -> None:
        project = config(tmp_path)
        lock, socket, record = paths
        loop = asyncio.get_running_loop()
        with (
            mock.patch("labnotes.daemon.server.fcntl.flock"),
            mock.patch.object(loop, "add_signal_handler") as handlers,
            mock.patch("labnotes.daemon.server.IDLE_SECONDS", 100),
        ):
            serving = asyncio.create_task(serve_daemon(project, "exp"))
            for _ in range(100):
                if handlers.call_count == 3:
                    break
                await asyncio.sleep(0.01)
            assert handlers.call_count == 3
            assert socket.stat().st_mode & 0o777 == 0o600
            assert record.stat().st_mode & 0o777 == 0o600
            handlers.call_args_list[0].args[1]()
            await asyncio.wait_for(serving, timeout=2)
        assert not record.exists()
        assert lock.stat().st_mode & 0o777 == 0o600

    asyncio.run(drive())


def test_commands_from_the_wire_reach_their_handlers(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        controls = mock.Mock()
        daemon.active["one"] = Invocation(controls=controls)

        async def send(line: str) -> dict[str, object]:
            return await daemon.dispatch(json.loads(line))

        assert await send('{"command": "restart", "options": {}}') == {
            "ok": False,
            "error": "restart needs run_id",
        }
        assert await send('{"command": "stop_one", "run": "r"}') == {"ok": True}
        assert await send('{"command": "set_concurrency", "count": 1}') == {"ok": True}
        assert await send('{"command": "stop_all"}') == {"ok": True}
        controls.kill.assert_called_once_with("r")
        controls.set_concurrency.assert_called_once_with(1)
        controls.interrupt.assert_called_once_with()
        for name in ("aaa", "zzz"):
            assert await send(json.dumps({"command": name})) == {
                "ok": False,
                "error": f"Unknown command {name}",
            }

    asyncio.run(drive())


def test_idle_exit_waits_five_seconds_after_last_busy(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        daemon.last_busy = 3.0
        with (
            mock.patch(
                "labnotes.daemon.server.time.monotonic", side_effect=[7.0, 7.9, 8.0]
            ),
            mock.patch(
                "labnotes.daemon.server.asyncio.sleep", new=mock.AsyncMock()
            ) as sleep,
        ):
            await daemon.wait_until_idle()
        assert sleep.await_args_list == [mock.call(0.2), mock.call(0.2)]

    asyncio.run(drive())


def test_server_creates_its_folder_and_waits_for_invocations(tmp_path: Path) -> None:
    lock = tmp_path / "state" / "labnotes" / "daemon.lock"
    record = tmp_path / "socket.record"
    finished: list[str] = []

    class Daemon(ExperimentDaemon):
        async def wait_until_idle(self) -> None:
            async def run() -> None:
                await asyncio.sleep(0.01)
                finished.append("run")

            self.active["one"] = Invocation(task=asyncio.create_task(run()))
            record.unlink()

    with (
        mock.patch("labnotes.daemon.server.lock_path", return_value=lock),
        mock.patch(
            "labnotes.daemon.server.socket_path", return_value=tmp_path / "d.sock"
        ),
        mock.patch("labnotes.daemon.server.socket_record", return_value=record),
        mock.patch("labnotes.daemon.server.ExperimentDaemon", Daemon),
    ):
        asyncio.run(serve_daemon(config(tmp_path), "exp"))
    assert lock.exists()
    assert finished == ["run"]


def test_start_reserves_runs_planned_by_live_invocations(tmp_path: Path) -> None:
    planned: dict[str, object] = {
        "event": "planned",
        "runs": [{"run": "r1", "params": {"m": "a"}}],
    }
    later: dict[str, object] = {
        "event": "planned",
        "runs": [{"run": "r9", "params": {"m": "z"}}],
    }
    batches: dict[str, list[dict[str, object]]] = {
        "empty": [],
        "stopping": [
            {**planned, "runs": [{"run": "r2", "params": {"m": "b"}}]},
            {"event": "stopping"},
        ],
        "live": [{"event": "meta"}, planned, later, {"event": "tearing down"}],
        "unplanned": [{"event": "setting up"}],
    }

    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        for batch, events in batches.items():
            daemon.active[batch] = Invocation(events=events)
        selected = mock.Mock(batch="new")

        async def fail_early(report, listen):
            raise ValueError("stop here")

        selected.side_effect = fail_early
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ) as start:
            await daemon.start({"environment": {"KEY": "value"}})
        assert start.call_args.args[14:16] == (
            {"r1": {"m": "a"}},
            {"KEY": "value"},
        )

    asyncio.run(drive())


def test_restart_with_a_run_id_starts_that_run(tmp_path: Path) -> None:
    daemon = ExperimentDaemon(config(tmp_path), "exp")
    options = {"run_id": "r"}
    with mock.patch.object(daemon, "start", return_value={"ok": True}) as start:
        reply = asyncio.run(daemon.dispatch({"command": "restart", "options": options}))
    assert reply == {"ok": True}
    start.assert_called_once_with(options, mock.ANY)


def test_batches_lists_active_invocations_in_start_order(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        assert await daemon.dispatch({"command": "batches"}) == {
            "ok": True,
            "batches": [],
        }
        daemon.active["b"] = Invocation()
        daemon.active["a"] = Invocation()
        assert await daemon.dispatch({"command": "batches"}) == {
            "ok": True,
            "batches": ["b", "a"],
        }

    asyncio.run(drive())


def test_server_never_unlinks_a_live_daemons_socket(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    _, live, record = paths
    live.touch()
    with (
        mock.patch("labnotes.daemon.server.listening", return_value=True) as probe,
        mock.patch("labnotes.daemon.server.uvicorn.Server") as bind,
    ):
        asyncio.run(serve_daemon(config(tmp_path), "exp"))
    probe.assert_called_once_with(live)
    bind.assert_not_called()
    assert live.exists()
    assert not record.exists()


def test_server_marks_run_state_as_live(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    with mock.patch("labnotes.daemon.server.IDLE_SECONDS", 0):
        asyncio.run(serve_daemon(config(tmp_path), "exp"))
    marker = Path(os.environ["XDG_STATE_HOME"]) / "labnotes/run-state/README"
    assert "Do not delete" in marker.read_text()


def test_start_publishes_runner_events_and_retains_daemon_errors(
    tmp_path: Path,
) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        batch = "b1"
        planned = {"event": "planned", "at": 1.0}
        failed = {"event": "daemon error", "error": "oops", "at": 2.0}
        selected = mock.Mock(batch=batch)
        queue: Queued = asyncio.Queue()
        daemon.subscribers.add(queue)

        async def run(report, listen):
            report(planned)
            listen(mock.Mock())
            raise ValueError("oops")

        selected.side_effect = run
        with (
            mock.patch(
                "labnotes.daemon.server.start_experiment", return_value=selected
            ),
            mock.patch(
                "labnotes.daemon.server.stamp_event", return_value=failed
            ) as stamp,
        ):
            assert await daemon.start({}) == {"ok": True, "batch": batch}
        assert daemon.history[batch].events == [planned, failed]
        assert not daemon.active
        assert [queue.get_nowait() for _ in range(queue.qsize())] == [
            (batch, planned),
            (batch, failed),
        ]
        stamp.assert_called_once_with({"event": "daemon error", "error": "oops"})

    asyncio.run(drive())


class Exchange:
    """Drive the daemon's ASGI app for one request, as uvicorn would."""

    def __init__(
        self, daemon: ExperimentDaemon, method: str, path: str, body: bytes = b""
    ) -> None:
        self.body: bytes | None = body
        self.sent: asyncio.Queue[Any] = asyncio.Queue()
        self.left = asyncio.Event()
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"labnotes")],
            "server": ("labnotes", 80),
            "client": None,
        }
        self.task = asyncio.create_task(daemon(scope, self.receive, self.sent.put))

    async def receive(self) -> dict[str, object]:
        if self.body is not None:
            body, self.body = self.body, None
            return {"type": "http.request", "body": body, "more_body": False}
        await self.left.wait()
        return {"type": "http.disconnect"}

    async def start(self) -> tuple[int, str]:
        message = await asyncio.wait_for(self.sent.get(), 1)
        assert message["type"] == "http.response.start"
        headers = dict(message["headers"])
        return int(message["status"]), headers[b"content-type"].decode()

    async def chunk(self) -> bytes:
        message = await asyncio.wait_for(self.sent.get(), 1)
        return bytes(message["body"])

    async def json(self) -> tuple[int, object]:
        status, kind = await self.start()
        assert kind == "application/json"
        body = await self.chunk()
        await asyncio.wait_for(self.task, 1)
        return status, json.loads(body)

    async def rest(self) -> bytes:
        await asyncio.wait_for(self.task, 1)
        chunks = []
        while not self.sent.empty():
            chunks.append(bytes(self.sent.get_nowait()["body"]))
        return b"".join(chunks)

    async def leave(self) -> None:
        self.left.set()
        await asyncio.wait_for(self.task, 1)


def test_routes_reply_with_json_and_status_by_outcome(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        controls = mock.Mock()
        daemon.active["one"] = Invocation(controls=controls)

        async def answer(
            method: str, path: str, body: bytes = b""
        ) -> tuple[int, object]:
            return await Exchange(daemon, method, path, body).json()

        assert await answer("GET", "/batches") == (
            200,
            {"ok": True, "batches": ["one"]},
        )
        assert await answer("POST", "/concurrency", b'{"count": 2}') == (
            200,
            {"ok": True},
        )
        controls.set_concurrency.assert_called_once_with(2)
        assert await answer("POST", "/concurrency", b'{"count": 0}') == (
            400,
            {"ok": False, "error": "count must be positive"},
        )
        assert await answer("POST", "/concurrency", b"not json") == (400, INVALID)
        assert await answer("POST", "/concurrency", b"[]") == (400, INVALID)
        assert await answer("POST", "/concurrency") == (
            400,
            {"ok": False, "error": "count must be positive"},
        )
        assert await answer("POST", "/runs/r7/stop") == (200, {"ok": True})
        controls.kill.assert_called_once_with("r7")
        assert await answer("POST", "/runs/r8/start") == (200, {"ok": True})
        controls.start_one.assert_called_once_with("r8")
        assert await answer("POST", "/finish-up") == (200, {"ok": True})
        controls.finish_up.assert_called_once_with()
        assert await answer("POST", "/stop") == (200, {"ok": True})
        controls.interrupt.assert_called_once_with()
        assert daemon.clients == 0

    asyncio.run(drive())


def test_unknown_route_and_method_are_refused(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        for method, path, status in (
            ("GET", "/nowhere", 404),
            ("GET", "/stop", 405),
            ("POST", "/batches", 405),
        ):
            exchange = Exchange(daemon, method, path)
            assert (await exchange.start())[0] == status
            await exchange.rest()

    asyncio.run(drive())


def test_handler_error_becomes_an_error_reply(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        with mock.patch.object(
            daemon, "dispatch", side_effect=ValueError("bad request")
        ):
            assert await Exchange(daemon, "GET", "/batches").json() == (
                400,
                {"ok": False, "error": "bad request"},
            )

    asyncio.run(drive())


@pytest.mark.parametrize("route", ["start", "restart"])
def test_start_streams_steps_before_its_reply(tmp_path: Path, route: str) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        seen: list[dict[str, object]] = []

        async def dispatch(message, progress):
            seen.append(message)
            progress("Snapshotting repo")
            return {"ok": True, "batch": "b"}

        with mock.patch.object(daemon, "dispatch", new=dispatch):
            exchange = Exchange(daemon, "POST", f"/{route}", b'{"run_id": "r"}')
            assert await exchange.start() == (200, "text/event-stream; charset=utf-8")
            assert await exchange.rest() == (
                b'event: step\ndata: "Snapshotting repo"\n\n'
                b'event: reply\ndata: {"ok": true, "batch": "b"}\n\n'
            )
        assert seen == [{"command": route, "options": {"run_id": "r"}}]

    asyncio.run(drive())


def test_start_with_a_bad_body_is_refused(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        assert await Exchange(daemon, "POST", "/start", b"[1]").json() == (
            400,
            INVALID,
        )
        assert not daemon.starting

    asyncio.run(drive())


def test_start_continues_after_its_client_leaves(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        release = asyncio.Event()
        finished: list[str] = []

        async def dispatch(message, progress):
            progress("Preparing")
            await release.wait()
            finished.append("start")
            return {"ok": True}

        with mock.patch.object(daemon, "dispatch", new=dispatch):
            exchange = Exchange(daemon, "POST", "/start")
            await exchange.start()
            assert await exchange.chunk() == b'event: step\ndata: "Preparing"\n\n'
            await exchange.leave()
            [task] = daemon.starting
            release.set()
            await asyncio.wait_for(task, 1)
        assert finished == ["start"]
        assert not daemon.starting
        assert daemon.clients == 0

    asyncio.run(drive())


def test_events_name_batches_then_replay_then_follow(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        old = [{"event": "planned", "at": 1}, {"event": "idle", "at": 2}]
        daemon.history["ended"] = Invocation(events=old)
        daemon.active["live"] = daemon.history["live"] = Invocation()
        exchange = Exchange(daemon, "GET", "/events")
        assert await exchange.start() == (200, "text/event-stream; charset=utf-8")
        assert (
            await exchange.chunk() == b'event: batches\ndata: {"batches": ["live"]}\n\n'
        )
        assert daemon.clients == 1
        for event in old:
            assert json.loads((await exchange.chunk()).removeprefix(b"data: ")) == {
                "batch": "ended",
                "event": event,
            }
        event = {"event": "planned", "at": 3}
        daemon.report("live", event)
        assert await exchange.chunk() == (
            b'data: {"batch": "live", "event": {"event": "planned", "at": 3}}\n\n'
        )
        await exchange.leave()
        assert not daemon.subscribers
        assert daemon.clients == 0

    asyncio.run(drive())


def test_ended_streams_close_their_responses(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        exchange = Exchange(daemon, "GET", "/events")
        await exchange.start()
        await exchange.chunk()
        assert len(daemon.subscribers) == 1
        daemon.end_streams()
        assert not daemon.subscribers
        assert await exchange.rest() == b""
        assert daemon.clients == 0

    asyncio.run(drive())


def test_full_subscriber_is_dropped_and_ended_without_blocking_others(
    tmp_path: Path,
) -> None:
    daemon = ExperimentDaemon(config(tmp_path), "exp")
    daemon.history["batch"] = Invocation()
    slow: Queued = asyncio.Queue()
    fast: Queued = asyncio.Queue()
    daemon.subscribers.update((slow, fast))
    first: dict[str, object] = {"event": "planned"}
    second: dict[str, object] = {"event": "idle"}
    with mock.patch("labnotes.daemon.server.MAX_QUEUED_EVENTS", 2):
        daemon.report("batch", first)
        fast.get_nowait()
        daemon.report("batch", second)
        assert slow in daemon.subscribers
        daemon.report("batch", second)
    assert daemon.history["batch"].events == [first, second, second]
    assert slow not in daemon.subscribers
    assert [slow.get_nowait() for _ in range(4)] == [
        ("batch", first),
        ("batch", second),
        ("batch", second),
        None,
    ]
    assert fast in daemon.subscribers
    assert fast.qsize() == 2


def test_subscriber_is_dropped_past_the_real_cap(tmp_path: Path) -> None:
    daemon = ExperimentDaemon(config(tmp_path), "exp")
    daemon.history["batch"] = Invocation()
    full: Queued = asyncio.Queue()
    for _ in range(99_999):
        full.put_nowait(None)
    daemon.subscribers.add(full)
    daemon.report("batch", {"event": "idle"})
    assert full in daemon.subscribers
    daemon.report("batch", {"event": "idle"})
    assert full not in daemon.subscribers
    assert full.qsize() == 100_002


def test_subscriber_at_a_large_cap_is_dropped(tmp_path: Path) -> None:
    daemon = ExperimentDaemon(config(tmp_path), "exp")
    daemon.history["batch"] = Invocation()
    full: Queued = asyncio.Queue()
    for _ in range(300):
        full.put_nowait(None)
    daemon.subscribers.add(full)
    with mock.patch("labnotes.daemon.server.MAX_QUEUED_EVENTS", 300):
        daemon.report("batch", {"event": "idle"})
    assert full not in daemon.subscribers


def test_server_answers_http_on_its_socket_and_ends_streams_on_close(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    async def drive() -> None:
        _, path, _ = paths
        loop = asyncio.get_running_loop()
        with (
            mock.patch("labnotes.daemon.server.fcntl.flock"),
            mock.patch.object(loop, "add_signal_handler") as handlers,
            mock.patch("labnotes.daemon.server.IDLE_SECONDS", 100),
        ):
            serving = asyncio.create_task(serve_daemon(config(tmp_path), "exp"))
            for _ in range(100):
                if handlers.call_count == 3:
                    break
                await asyncio.sleep(0.01)
            reader, writer = await asyncio.open_unix_connection(str(path))
            writer.write(b"GET /batches HTTP/1.1\r\nhost: labnotes\r\n\r\n")
            assert await reader.readline() == b"HTTP/1.1 200 OK\r\n"
            await reader.readuntil(b"\r\n\r\n")
            assert json.loads(await reader.readuntil(b"}")) == {
                "ok": True,
                "batches": [],
            }
            writer.write(b"GET /events HTTP/1.1\r\nhost: labnotes\r\n\r\n")
            assert b"event: batches\n" in await reader.readuntil(b"\n\n")
            handlers.call_args_list[0].args[1]()
            await asyncio.wait_for(serving, timeout=0.9)
            assert (await reader.read()).endswith(b"0\r\n\r\n")
            writer.close()
        assert not path.exists()

    asyncio.run(drive())


def test_start_one_asks_every_active_invocation_to_start_that_run(
    tmp_path: Path,
) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        first, second = mock.Mock(), mock.Mock()
        daemon.active["one"] = Invocation(controls=first)
        daemon.active["two"] = Invocation(controls=second)
        daemon.active["three"] = Invocation()

        line = '{"command": "start_one", "run": "r"}'
        assert await daemon.dispatch(json.loads(line)) == {"ok": True}
        assert await daemon.dispatch({"command": "start_one"}) == {
            "ok": False,
            "error": "start_one needs a run id",
        }
        first.start_one.assert_called_once_with("r")
        second.start_one.assert_called_once_with("r")

    asyncio.run(drive())
