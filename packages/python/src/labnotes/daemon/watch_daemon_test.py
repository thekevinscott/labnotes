import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.daemon.watch_daemon import TAIL_SECONDS, watch_daemon


class Gone(Exception):
    pass


def message(event: dict[str, object]) -> mock.Mock:
    return mock.Mock(json=mock.Mock(return_value=event))


@pytest.fixture
def daemon() -> Iterator[dict[str, Any]]:
    client = mock.MagicMock()
    response = client.stream.return_value.__aenter__.return_value
    sent: list[object] = [{"event": "connected", "client": 7}]

    async def stream(_: object) -> AsyncIterator[mock.Mock]:
        for item in sent:
            if isinstance(item, Exception):
                raise item
            if callable(item):
                await item()
                continue
            yield message(item)  # type: ignore[arg-type]

    with (
        mock.patch("labnotes.daemon.watch_daemon.daemon_client") as daemon_client,
        mock.patch("labnotes.daemon.watch_daemon.httpx2") as httpx2,
        mock.patch("labnotes.daemon.watch_daemon.TAIL_SECONDS", 0.01),
    ):
        daemon_client.return_value.__aenter__.return_value = client
        httpx2.EventSource.side_effect = stream
        httpx2.TransportError = Gone
        yield {
            "client": client,
            "response": response,
            "sent": sent,
            "daemon_client": daemon_client,
            "event_source": httpx2.EventSource,
        }


def watch(follow: bool) -> list[dict[str, object]]:
    emitted: list[dict[str, object]] = []
    asyncio.run(watch_daemon(Path("/p"), follow, emitted.append))
    return emitted


def started(folder: Path) -> dict[str, object]:
    return {"event": "started", "experiment": "exp", "run": "r1", "folder": str(folder)}


def output(line: str) -> dict[str, object]:
    return {
        "event": "output",
        "experiment": "exp",
        "run": "r1",
        "stream": "stdout",
        "line": line,
    }


def test_reports_the_daemons_state_then_stops(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    (tmp_path / "stdout.log").write_text("one\ntwo\n")
    daemon["sent"].extend([started(tmp_path), {"event": "replayed"}, {"event": "idle"}])

    assert watch(follow=False) == [started(tmp_path), output("two")]
    daemon["daemon_client"].assert_called_once_with(Path("/p"))
    daemon["client"].stream.assert_called_once_with(
        "GET", "/events", params={"watch": "1"}
    )
    daemon["event_source"].assert_called_once_with(daemon["response"])


def test_follows_events_and_new_log_lines(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    log = tmp_path / "stdout.log"

    async def write() -> None:
        log.write_text("one\n")
        await asyncio.sleep(0.05)

    daemon["sent"].extend(
        [
            {"event": "replayed"},
            started(tmp_path),
            write,
            {"event": "queued", "experiment": "exp", "run": "r2"},
        ]
    )

    assert watch(follow=True) == [
        started(tmp_path),
        output("one"),
        {"event": "queued", "experiment": "exp", "run": "r2"},
    ]


def test_reads_a_runs_last_lines_before_it_ends(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    log = tmp_path / "stdout.log"
    ended = {"event": "ended", "experiment": "exp", "run": "r1", "exit_code": 0}

    async def write() -> None:
        log.write_text("last\n")

    daemon["sent"].extend(
        [{"event": "replayed"}, started(tmp_path), write, ended, write]
    )

    assert watch(follow=True) == [started(tmp_path), output("last"), ended]


def test_stops_when_the_daemon_goes_away(daemon: dict[str, Any]) -> None:
    daemon["sent"].extend([{"event": "replayed"}, {"event": "idle"}, Gone()])

    assert watch(follow=True) == [{"event": "idle"}]


def test_stops_when_the_daemon_cannot_be_reached(daemon: dict[str, Any]) -> None:
    daemon["client"].stream.side_effect = Gone()

    assert watch(follow=True) == []


def test_reads_logs_once_a_second() -> None:
    assert TAIL_SECONDS == 1.0
