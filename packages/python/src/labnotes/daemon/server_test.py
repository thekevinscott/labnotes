import asyncio
import json
import os
import socket
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

from labnotes.daemon.server import ExperimentDaemon, Invocation, serve_daemon


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
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "one.jsonl"))

        async def run(report, listen):
            listen(controls)
            await done.wait()
            return []

        selected.side_effect = run
        with mock.patch(
            "labnotes.daemon.server.start_experiment", return_value=selected
        ):
            assert await daemon.dispatch({"command": "ping"}) == {"ok": True}
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
                "journal": str(tmp_path / "one.jsonl"),
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
                    {"command": "set_concurrency", "count": 2, "journal": "missing"}
                )
            )["ok"] is False
            assert await daemon.dispatch(
                {
                    "command": "set_concurrency",
                    "count": 2,
                    "journal": str(tmp_path / "one.jsonl"),
                }
            ) == {"ok": True}
            assert await daemon.dispatch(
                {"command": "set_concurrency", "count": 3}
            ) == {"ok": True}
            assert set_concurrency.call_args_list == [
                mock.call(2),
                mock.call(3),
            ]
            assert await daemon.dispatch({"command": "attach"}) == {
                "ok": True,
                "journals": [str(tmp_path / "one.jsonl")],
            }
            assert await daemon.dispatch({"command": "finish_up"}) == {"ok": True}
            controls.finish_up.assert_called_once_with()
            assert (await daemon.dispatch({"command": "unknown"}))["ok"] is False
            assert await daemon.dispatch({"command": "stop_all"}) == {"ok": True}
            await asyncio.sleep(0)
            assert not daemon.active
            finish.assert_called_once_with()

    asyncio.run(drive())


def test_finished_up_journal_releases_planned_runs_from_reservations(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "finished_up.jsonl"
    journal.write_text(
        json.dumps({"event": "planned", "runs": [{"run": "r1", "params": {"m": "a"}}]})
        + "\n"
        + json.dumps({"event": "finishing up"})
        + "\n"
    )

    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        daemon.active[str(journal)] = Invocation()
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "new.jsonl"))

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
    daemon.active[str(tmp_path / "active.jsonl")] = Invocation(controls=controls)

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
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "new.jsonl"))

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
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "one.jsonl"))

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
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "bad.jsonl"))

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
        selected.run_state.record.assert_called_once_with(
            {"event": "daemon error", "error": "run failed"}
        )
        assert not daemon.active

    asyncio.run(drive())


def test_start_waits_for_slow_preparation_without_a_deadline(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "slow.jsonl"))

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
                "journal": str(tmp_path / "slow.jsonl"),
            }

    asyncio.run(drive())


def test_start_that_ends_before_any_run_reports_it(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "none.jsonl"))

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
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "one.jsonl"))

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
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "one.jsonl"))

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
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "pending.jsonl"))

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


def test_socket_replies_once_and_attach_holds_connection(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        server = await asyncio.start_unix_server(
            daemon.handle, path=str(tmp_path / "s.sock")
        )
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(tmp_path / "s.sock")
            )
            writer.write(b'{"command":"attach"}\n')
            await writer.drain()
            assert json.loads(await reader.readline()) == {
                "ok": True,
                "journals": [],
            }
            assert daemon.clients == 1
            writer.close()
            await writer.wait_closed()
            await asyncio.sleep(0)

            for payload, expected in (
                (b"[]\n", "Request must be an object"),
                (b"not json\n", "Invalid request"),
            ):
                reader, writer = await asyncio.open_unix_connection(
                    str(tmp_path / "s.sock")
                )
                writer.write(payload)
                await writer.drain()
                assert json.loads(await reader.readline()) == {
                    "ok": False,
                    "error": expected,
                }
                writer.close()
                await writer.wait_closed()
            reader, writer = await asyncio.open_unix_connection(
                str(tmp_path / "s.sock")
            )
            writer.close()
            await writer.wait_closed()
            for _ in range(20):
                if daemon.clients == 0:
                    break
                await asyncio.sleep(0.01)
            assert daemon.clients == 0
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(drive())


def test_socket_reports_handler_error(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        server = await asyncio.start_unix_server(
            daemon.handle, path=str(tmp_path / "s.sock")
        )
        try:
            with mock.patch.object(
                daemon, "dispatch", side_effect=ValueError("bad request")
            ):
                reader, writer = await asyncio.open_unix_connection(
                    str(tmp_path / "s.sock")
                )
                writer.write(b'{"command":"start"}\n')
                await writer.drain()
                assert json.loads(await reader.readline()) == {
                    "ok": False,
                    "error": "bad request",
                }
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

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
        sleep.assert_awaited_once_with(0.1)
        assert not record.exists()

    asyncio.run(drive())


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

        assert await send('{"command": "ping"}') == {"ok": True}
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


def test_socket_closes_after_one_reply_unless_attached(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        server = await asyncio.start_unix_server(
            daemon.handle, path=str(tmp_path / "s.sock")
        )
        try:
            for payload in (b'{"command":"ping"}\n', b'{"command":"aaa"}\n'):
                reader, writer = await asyncio.open_unix_connection(
                    str(tmp_path / "s.sock")
                )
                writer.write(payload)
                await writer.drain()
                await reader.readline()
                assert await asyncio.wait_for(reader.read(), timeout=1) == b""
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(drive())


def test_start_steps_reach_the_wire_before_the_reply(tmp_path: Path) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")

        async def dispatch(message, progress):
            progress("Snapshotting repo")
            return {"ok": True}

        server = await asyncio.start_unix_server(
            daemon.handle, path=str(tmp_path / "s.sock")
        )
        try:
            with mock.patch.object(daemon, "dispatch", new=dispatch):
                reader, writer = await asyncio.open_unix_connection(
                    str(tmp_path / "s.sock")
                )
                writer.write(b'{"command":"start","options":{}}\n')
                await writer.drain()
                assert await reader.read() == (
                    b'{"step": "Snapshotting repo"}\n{"ok": true}\n'
                )
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

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
    planned = {"event": "planned", "runs": [{"run": "r1", "params": {"m": "a"}}]}
    later = {"event": "planned", "runs": [{"run": "r9", "params": {"m": "z"}}]}
    live = tmp_path / "live.jsonl"
    live.write_text(
        "\n".join(
            json.dumps(e)
            for e in ({"event": "meta"}, planned, later, {"event": "tearing down"})
        )
        + "\n"
    )
    unplanned = tmp_path / "unplanned.jsonl"
    unplanned.write_text(json.dumps({"event": "setting up"}) + "\n")
    stopping = tmp_path / "stopping.jsonl"
    stopping.write_text(
        json.dumps({**planned, "runs": [{"run": "r2", "params": {"m": "b"}}]})
        + "\n"
        + json.dumps({"event": "stopping"})
        + "\n"
    )

    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        for path in (tmp_path / "gone.jsonl", stopping, live, unplanned):
            daemon.active[str(path)] = Invocation()
        selected = mock.Mock(run_state=mock.Mock(path=tmp_path / "new.jsonl"))

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


@pytest.mark.parametrize("action", ["attach", "journals"])
def test_attach_and_journals_list_active_invocations_in_start_order(
    tmp_path: Path, action: str
) -> None:
    async def drive() -> None:
        daemon = ExperimentDaemon(config(tmp_path), "exp")
        assert await daemon.dispatch({"command": action}) == {
            "ok": True,
            "journals": [],
        }
        daemon.active["b.jsonl"] = Invocation()
        daemon.active["a.jsonl"] = Invocation()
        assert await daemon.dispatch({"command": action}) == {
            "ok": True,
            "journals": ["b.jsonl", "a.jsonl"],
        }

    asyncio.run(drive())


def test_server_never_unlinks_a_live_daemons_socket(tmp_path: Path) -> None:
    with TemporaryDirectory(prefix="ln-") as folder:
        live = Path(folder) / "live.sock"
        record = tmp_path / "socket.record"
        with (
            socket.socket(socket.AF_UNIX) as other,
            mock.patch(
                "labnotes.daemon.server.lock_path", return_value=tmp_path / "d.lock"
            ),
            mock.patch("labnotes.daemon.server.socket_path", return_value=live),
            mock.patch("labnotes.daemon.server.socket_record", return_value=record),
            mock.patch("labnotes.daemon.server.IDLE_SECONDS", 0),
        ):
            other.bind(str(live))
            other.listen()
            asyncio.run(serve_daemon(config(tmp_path), "exp"))
            assert live.exists()
            assert not record.exists()


def test_server_marks_run_state_as_live(
    tmp_path: Path, paths: tuple[Path, Path, Path]
) -> None:
    with mock.patch("labnotes.daemon.server.IDLE_SECONDS", 0):
        asyncio.run(serve_daemon(config(tmp_path), "exp"))
    marker = Path(os.environ["XDG_STATE_HOME"]) / "labnotes/run-state/README"
    assert "live" in marker.read_text()
