import asyncio
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import httpx2
import pytest

from labnotes.daemon.attachment import STREAM_LIMIT, Attachment

Handler = Callable[[httpx2.Request], httpx2.Response]


def opened(path: Path | None, handler: Handler) -> Attachment:
    with (
        mock.patch("labnotes.daemon.attachment.daemon_socket", return_value=path),
        mock.patch(
            "labnotes.daemon.attachment.httpx2.AsyncHTTPTransport",
            return_value=httpx2.MockTransport(handler),
        ) as transport,
    ):
        attachment = asyncio.run(Attachment.open(mock.Mock(), "exp"))
    transport.assert_called_once_with(uds=str(path))
    return attachment


def streaming(body: bytes, seen: list[httpx2.Request] | None = None) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )

    return handler


def collect(attachment: Attachment) -> list[tuple[str, dict[str, object]]]:
    async def drive() -> list[tuple[str, dict[str, object]]]:
        try:
            return [item async for item in attachment]
        finally:
            await attachment.aclose()

    return asyncio.run(drive())


def test_attachment_names_batches_then_yields_events(tmp_path: Path) -> None:
    seen: list[httpx2.Request] = []
    attachment = opened(
        tmp_path / "d.sock",
        streaming(
            b'event: batches\ndata: {"batches": ["b1", "b2"]}\n\n'
            b'data: {"batch": "b1", "event": {"event": "planned"}}\n\n'
            b'data: {"batch": "b2", "event": {"event": "idle"}}\n\n',
            seen,
        ),
    )
    assert attachment.batches == ["b1", "b2"]
    [request] = seen
    assert (request.method, str(request.url)) == ("GET", "http://labnotes/events")
    assert request.extensions["timeout"]["connect"] == 10
    assert request.extensions["timeout"]["read"] is None
    assert collect(attachment) == [
        ("b1", {"event": "planned"}),
        ("b2", {"event": "idle"}),
    ]
    assert attachment.client.is_closed
    assert attachment.response.is_closed


def test_attachment_reports_no_daemon() -> None:
    with mock.patch("labnotes.daemon.attachment.daemon_socket", return_value=None):
        with pytest.raises(ValueError, match="No daemon is running for exp."):
            asyncio.run(Attachment.open(mock.Mock(), "exp"))


@pytest.mark.parametrize(
    ("body", "said"),
    [
        (b'{"ok": false, "error": "busy"}', "busy"),
        (b'{"ok": false}', "Daemon rejected attach"),
    ],
)
def test_a_rejected_attach_says_why_and_closes(
    tmp_path: Path, body: bytes, said: str
) -> None:
    clients: list[httpx2.AsyncClient] = []
    real = httpx2.AsyncClient

    def client(**options: object) -> httpx2.AsyncClient:
        clients.append(real(**options))  # type: ignore[arg-type]
        return clients[-1]

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(409, content=body)

    with mock.patch("labnotes.daemon.attachment.httpx2.AsyncClient", new=client):
        with pytest.raises(ValueError, match=f"^{said}$"):
            opened(tmp_path / "d.sock", handler)
    assert clients[0].is_closed


@pytest.mark.parametrize(
    "handler",
    [
        streaming(b""),
        streaming(b": comment only\n\n"),
    ],
)
def test_a_stream_closed_before_naming_batches_says_so(
    tmp_path: Path, handler: Handler
) -> None:
    with pytest.raises(ValueError, match="^Daemon for exp closed without a reply.$"):
        opened(tmp_path / "d.sock", handler)


def test_a_transport_error_on_open_is_reported(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused")

    with pytest.raises(ValueError, match="^refused$"):
        opened(tmp_path / "d.sock", handler)


def test_a_bad_first_event_closes_the_client(tmp_path: Path) -> None:
    clients: list[httpx2.AsyncClient] = []
    real = httpx2.AsyncClient

    def client(**options: object) -> httpx2.AsyncClient:
        clients.append(real(**options))  # type: ignore[arg-type]
        return clients[-1]

    with mock.patch("labnotes.daemon.attachment.httpx2.AsyncClient", new=client):
        with pytest.raises(KeyError):
            opened(tmp_path / "d.sock", streaming(b"data: {}\n\n"))
    assert clients[0].is_closed


def test_events_up_to_the_stream_limit_are_read(tmp_path: Path) -> None:
    head = b'data: {"batch": "b1", "event": {"pad": "'
    tail = b'"}}'
    pad = b"x" * (STREAM_LIMIT - len(head) - len(tail) - 1)
    attachment = opened(
        tmp_path / "d.sock",
        streaming(
            b'event: batches\ndata: {"batches": []}\n\n' + head + pad + tail + b"\n\n"
        ),
    )
    [(batch, event)] = collect(attachment)
    assert (batch, len(str(event["pad"]))) == ("b1", len(pad))


def test_an_event_over_the_stream_limit_ends_with_an_error(
    tmp_path: Path,
) -> None:
    attachment = opened(
        tmp_path / "d.sock",
        streaming(
            b'event: batches\ndata: {"batches": []}\n\n'
            b"data: " + b"x" * (STREAM_LIMIT + 1) + b"\n\n"
        ),
    )
    with pytest.raises(ValueError):
        collect(attachment)
