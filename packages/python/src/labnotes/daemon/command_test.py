import json
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import httpx2
import pytest

from labnotes.daemon.command import command

Handler = Callable[[httpx2.Request], httpx2.Response]


def test_command_reports_no_daemon() -> None:
    with mock.patch("labnotes.daemon.command.daemon_socket", return_value=None):
        with pytest.raises(ValueError, match="No daemon is running"):
            command(mock.Mock(), "exp", {"command": "stop_all"})


def run_command(
    path: Path,
    handler: Handler,
    message: dict[str, object],
    progress: Callable[[str], None] | None = None,
    record: Path | None = None,
) -> dict[str, object]:
    # unit-lint only sees a patch target outside a `with` item.
    patcher = mock.patch(
        "httpx2.HTTPTransport", return_value=httpx2.MockTransport(handler)
    )
    transport = patcher.start()
    try:
        with (
            mock.patch("labnotes.daemon.command.daemon_socket", return_value=path),
            mock.patch(
                "labnotes.daemon.command.socket_record",
                return_value=record or path.with_suffix(".record"),
            ),
        ):
            reply = command(mock.Mock(), "exp", message, progress)
    finally:
        patcher.stop()
    transport.assert_called_once_with(uds=str(path))
    return reply


def replying(
    body: bytes, seen: list[httpx2.Request], kind: str = "application/json"
) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, headers={"content-type": kind}, content=body)

    return handler


def failing(error: type[Exception]) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise error("failed")  # type: ignore[call-arg]

    return handler


STREAMED = (
    b'event: step\ndata: "Snapshotting repo"\n\n'
    b'event: reply\ndata: {"ok": true, "batch": "b"}\n\n'
)


@pytest.mark.parametrize(
    ("message", "method", "route", "body"),
    [
        ({"command": "batches"}, "GET", "/batches", b""),
        ({"command": "stop_all"}, "POST", "/stop", b"{}"),
        ({"command": "finish_up"}, "POST", "/finish-up", b"{}"),
        (
            {"command": "set_concurrency", "count": 2, "batch": "b"},
            "POST",
            "/concurrency",
            b'{"count":2,"batch":"b"}',
        ),
        (
            {"command": "stop_one", "run": "r7"},
            "POST",
            "/runs/r7/stop",
            b'{"run":"r7"}',
        ),
        (
            {"command": "start_one", "run": "r7"},
            "POST",
            "/runs/r7/start",
            b'{"run":"r7"}',
        ),
    ],
)
def test_command_maps_each_action_to_its_route(
    tmp_path: Path, message: dict[str, object], method: str, route: str, body: bytes
) -> None:
    seen: list[httpx2.Request] = []
    reply = run_command(tmp_path / "d.sock", replying(b'{"ok": true}', seen), message)
    assert reply == {"ok": True}
    [request] = seen
    assert (request.method, str(request.url)) == (method, f"http://labnotes{route}")
    assert request.content == body
    assert request.extensions["timeout"] == {
        "connect": 10,
        "read": 10,
        "write": 10,
        "pool": 10,
    }


@pytest.mark.parametrize("action", ["start", "restart"])
def test_start_streams_steps_to_progress_and_waits_without_deadline(
    tmp_path: Path, action: str
) -> None:
    seen: list[httpx2.Request] = []
    steps: list[str] = []
    reply = run_command(
        tmp_path / "d.sock",
        replying(STREAMED, seen, "text/event-stream; charset=utf-8"),
        {"command": action, "options": {"run_id": "r"}},
        steps.append,
    )
    assert reply == {"ok": True, "batch": "b"}
    assert steps == ["Snapshotting repo"]
    [request] = seen
    assert str(request.url) == f"http://labnotes/{action}"
    assert json.loads(request.content) == {"run_id": "r"}
    assert request.extensions["timeout"]["read"] is None
    assert request.extensions["timeout"]["connect"] == 10


def test_start_without_options_or_progress_sends_an_empty_object(
    tmp_path: Path,
) -> None:
    seen: list[httpx2.Request] = []
    reply = run_command(
        tmp_path / "d.sock",
        replying(STREAMED, seen, "text/event-stream"),
        {"command": "start"},
    )
    assert reply == {"ok": True, "batch": "b"}
    assert seen[0].content == b"{}"


def test_an_error_reply_is_returned_as_is(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"ok": False, "error": "nope"})

    assert run_command(tmp_path / "d.sock", handler, {"command": "stop_all"}) == {
        "ok": False,
        "error": "nope",
    }


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (b'event: step\ndata: "Starting run"\n\n', "text/event-stream"),
        (b"not json", "application/json"),
        (b"[1]", "application/json"),
    ],
)
def test_command_reports_a_missing_reply_as_closed(
    tmp_path: Path, body: bytes, kind: str
) -> None:
    with pytest.raises(ValueError, match="Daemon for exp closed without a reply"):
        run_command(tmp_path / "d.sock", replying(body, [], kind), {"command": "start"})


def test_command_reports_a_reset_connection_as_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="closed without a reply"):
        run_command(
            tmp_path / "d.sock", failing(httpx2.ReadError), {"command": "stop_all"}
        )


@pytest.mark.parametrize(
    ("error", "said"),
    [
        (httpx2.ReadTimeout, "did not reply in 10s"),
        (httpx2.ConnectTimeout, "did not answer in 10s"),
    ],
)
def test_a_timeout_keeps_the_daemon_findable(
    tmp_path: Path, error: type[Exception], said: str
) -> None:
    path = tmp_path / "d.sock"
    record = tmp_path / "socket.record"
    path.touch()
    record.touch()
    with pytest.raises(ValueError, match=f"Daemon for exp {said}"):
        run_command(path, failing(error), {"command": "stop_all"}, record=record)
    assert path.exists()
    assert record.exists()


def test_failed_connect_cleans_stale_record(tmp_path: Path) -> None:
    path = tmp_path / "stale.sock"
    record = tmp_path / "socket.record"
    path.touch()
    record.touch()
    with pytest.raises(ValueError, match="No daemon is running for exp"):
        run_command(
            path, failing(httpx2.ConnectError), {"command": "batches"}, record=record
        )
    assert not path.exists()
    assert not record.exists()


def test_failed_connect_to_a_vanished_socket_still_reports_no_daemon(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="No daemon is running"):
        run_command(
            tmp_path / "gone",
            failing(httpx2.ConnectError),
            {"command": "batches"},
            record=tmp_path / "missing.record",
        )
