import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

import httpx2
import pytest

from labnotes.daemon.follow_route import MAX_EVENT_BYTES, follow_route

Handler = Callable[[httpx2.Request], httpx2.Response]


def replies(*bodies: tuple[int, bytes] | Exception) -> tuple[Handler, list[Any]]:
    seen: list[httpx2.Request] = []
    left = list(bodies)

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        reply = left.pop(0)
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        return httpx2.Response(
            status, headers={"content-type": "text/event-stream"}, content=body
        )

    return handler, seen


async def take(
    handler: Handler,
    count: int,
    sockets: list[Path | None],
    ensure: mock.AsyncMock,
    route: str = "/runs",
) -> list[tuple[str, Any]]:
    # unit-lint only sees a patch target outside a `with` item.
    patcher = mock.patch(
        "httpx2.AsyncHTTPTransport", return_value=httpx2.MockTransport(handler)
    )
    patcher.start()
    found: list[tuple[str, Any]] = []
    try:
        with (
            mock.patch(
                "labnotes.daemon.follow_route.daemon_socket", side_effect=sockets
            ),
            mock.patch("labnotes.daemon.follow_route.RETRY_SECONDS", 0),
        ):
            stream = follow_route(mock.Mock(), "exp", route, ensure)
            async for item in stream:
                found.append(item)
                if len(found) == count:
                    break
            await stream.aclose()
    finally:
        patcher.stop()
    return found


def test_yields_each_event_then_resumes_from_the_last_id_after_a_drop(
    tmp_path: Path,
) -> None:
    handler, seen = replies(
        (200, b'event: state\nid: one\ndata: [1]\n\nevent: run\ndata: {"id": "a"}\n\n'),
        httpx2.ConnectError("refused"),
        (200, b"event: run\nid: two\ndata: 2\n\n"),
    )
    ensure = mock.AsyncMock()
    sock = tmp_path / "d.sock"
    found = asyncio.run(take(handler, 3, [sock, sock, sock], ensure))
    assert found == [("state", [1]), ("run", {"id": "a"}), ("run", 2)]
    assert [str(request.url) for request in seen] == ["http://labnotes/runs"] * 3
    assert "last-event-id" not in seen[0].headers
    assert [request.headers["last-event-id"] for request in seen[1:]] == [
        "one",
        "one",
    ]
    assert seen[0].extensions["timeout"]["read"] is None
    assert ensure.await_args_list == [mock.call(mock.ANY, "exp")] * 3


def test_waits_for_a_daemon_socket_before_connecting(tmp_path: Path) -> None:
    handler, seen = replies((200, b"event: state\ndata: null\n\n"))
    ensure = mock.AsyncMock()
    found = asyncio.run(take(handler, 1, [None, tmp_path / "d.sock"], ensure))
    assert found == [("state", None)]
    assert len(seen) == 1
    assert ensure.await_count == 2


def test_retries_when_starting_a_daemon_fails(tmp_path: Path) -> None:
    handler, seen = replies((200, b"event: state\ndata: null\n\n"))
    ensure = mock.AsyncMock(
        side_effect=[OSError("busy"), ValueError("exited during startup"), None]
    )
    found = asyncio.run(take(handler, 1, [tmp_path / "d.sock"], ensure))
    assert found == [("state", None)]
    assert len(seen) == 1
    assert ensure.await_count == 3


def test_a_rejected_route_raises_its_error(tmp_path: Path) -> None:
    handler, _ = replies((404, b'{"error": "No experiment"}'))
    with pytest.raises(ValueError, match="No experiment"):
        asyncio.run(take(handler, 1, [tmp_path / "d.sock"], mock.AsyncMock()))


def test_a_rejection_without_a_message_names_the_route(tmp_path: Path) -> None:
    handler, _ = replies((500, b"{}"))
    with pytest.raises(ValueError, match="/experiment"):
        asyncio.run(
            take(handler, 1, [tmp_path / "d.sock"], mock.AsyncMock(), "/experiment")
        )


def test_an_event_up_to_the_limit_is_read(tmp_path: Path) -> None:
    head, tail = b'data: "', b'"'
    pad = b"x" * (MAX_EVENT_BYTES - len(head) - len(tail) - 1)
    handler, _ = replies((200, head + pad + tail + b"\n\n"))
    [(_, data)] = asyncio.run(take(handler, 1, [tmp_path / "d.sock"], mock.AsyncMock()))
    assert len(data) == len(pad)
