import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.daemon.watch_daemon import TAIL_SECONDS, USAGE_SECONDS, watch_daemon


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
        mock.patch(
            "labnotes.daemon.watch_daemon.run_usage",
            new=mock.AsyncMock(return_value={"memory": 5, "size": 9}),
        ) as run_usage,
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
            "run_usage": run_usage,
        }


def watch(follow: bool) -> list[dict[str, object]]:
    emitted: list[dict[str, object]] = []
    asyncio.run(watch_daemon(Path("/p"), follow, emitted.append))
    return emitted


def started(folder: Path) -> dict[str, object]:
    return {"event": "started", "experiment": "exp", "run": "r1", "folder": str(folder)}


USAGE = {"event": "usage", "experiment": "exp", "run": "r1", "memory": 5, "size": 9}


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

    assert watch(follow=False) == [started(tmp_path), output("two"), USAGE]
    daemon["run_usage"].assert_awaited_once_with(tmp_path, True)
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


def test_samples_running_runs_again_while_following(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    async def wait() -> None:
        await asyncio.sleep(0.05)

    daemon["sent"].extend([started(tmp_path), {"event": "replayed"}, wait])

    with mock.patch("labnotes.daemon.watch_daemon.USAGE_SECONDS", 0.01):
        emitted = watch(follow=True)

    assert emitted[:2] == [started(tmp_path), USAGE]
    assert emitted.count(USAGE) > 2


def test_stops_sampling_a_run_once_it_ends(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    ended = {"event": "ended", "experiment": "exp", "run": "r1", "exit_code": 0}

    async def wait() -> None:
        await asyncio.sleep(0.05)

    daemon["sent"].extend([started(tmp_path), {"event": "replayed"}, ended, wait])

    with mock.patch("labnotes.daemon.watch_daemon.USAGE_SECONDS", 0.01):
        emitted = watch(follow=True)

    assert emitted == [started(tmp_path), USAGE, ended]


def test_drops_a_sample_that_finishes_after_its_run_ended(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    paused, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def sample(folder: Path, running: bool) -> dict[str, int | None]:
        nonlocal calls
        calls += 1
        if calls == 4:
            paused.set()
            await release.wait()
        return {"memory": 5, "size": 9}

    daemon["run_usage"].side_effect = sample
    second = {**started(tmp_path / "r2"), "run": "r2"}
    third = {**started(tmp_path / "r3"), "run": "r3"}

    def ended(run: str) -> dict[str, object]:
        return {"event": "ended", "experiment": "exp", "run": run, "exit_code": 0}

    async def let_go() -> None:
        release.set()
        for _ in range(5):
            await asyncio.sleep(0)

    daemon["sent"].extend(
        [
            started(tmp_path),
            second,
            third,
            {"event": "replayed"},
            paused.wait,
            ended("r1"),
            ended("r2"),
            let_go,
        ]
    )

    with mock.patch("labnotes.daemon.watch_daemon.USAGE_SECONDS", 0.01):
        emitted = watch(follow=True)

    assert emitted == [
        started(tmp_path),
        second,
        third,
        USAGE,
        {**USAGE, "run": "r2"},
        {**USAGE, "run": "r3"},
        ended("r1"),
        ended("r2"),
        {**USAGE, "run": "r3"},
    ]
    assert daemon["run_usage"].await_args_list[3:] == [
        mock.call(tmp_path, True),
        mock.call(tmp_path / "r3", True),
    ]


def test_stops_tailing_and_sampling_once_the_stream_ends(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    daemon["sent"].extend([started(tmp_path), {"event": "replayed"}])
    emitted: list[dict[str, object]] = []

    async def go() -> None:
        await watch_daemon(Path("/p"), True, emitted.append)
        sampled = daemon["run_usage"].await_count
        await asyncio.sleep(0.05)
        assert daemon["run_usage"].await_count == sampled

    with mock.patch("labnotes.daemon.watch_daemon.USAGE_SECONDS", 0.01):
        asyncio.run(go())


def test_samples_usage_every_thirty_seconds() -> None:
    assert USAGE_SECONDS == 30.0


def ended(exit_code: int | None, **extra: object) -> dict[str, object]:
    return {
        "event": "ended",
        "experiment": "exp",
        "run": "r1",
        "exit_code": exit_code,
        **extra,
    }


def endings(emitted: list[dict[str, object]]) -> list[dict[str, object]]:
    return [event for event in emitted if event["event"] == "ended"]


@pytest.mark.parametrize(
    "result",
    [
        {"exit_code": 1},
        {"exit_code": -15, "ended_by": "signal"},
        {"exit_code": None, "error": "no shell"},
    ],
)
def test_adds_the_last_stderr_line_when_a_run_fails(
    tmp_path: Path, daemon: dict[str, Any], result: dict[str, object]
) -> None:
    (tmp_path / "stderr.log").write_text("Traceback\nValueError: boom\n\n")
    failed = {**ended(None), **result}
    daemon["sent"].extend([started(tmp_path), failed, {"event": "replayed"}])

    assert endings(watch(follow=False)) == [
        {**failed, "last_stderr": "ValueError: boom"}
    ]


def test_leaves_a_passing_runs_stderr_alone(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    (tmp_path / "stderr.log").write_text("warning: noisy\n")
    daemon["sent"].extend([started(tmp_path), ended(0), {"event": "replayed"}])

    assert endings(watch(follow=False)) == [ended(0)]


@pytest.mark.parametrize("log", [None, "", "\n  \n"])
def test_adds_nothing_without_stderr(
    tmp_path: Path, daemon: dict[str, Any], log: str | None
) -> None:
    if log is not None:
        (tmp_path / "stderr.log").write_text(log)
    daemon["sent"].extend([started(tmp_path), ended(1), {"event": "replayed"}])

    assert endings(watch(follow=False)) == [ended(1)]


def test_adds_nothing_for_a_run_it_never_saw_start(daemon: dict[str, Any]) -> None:
    daemon["sent"].extend([ended(1), {"event": "replayed"}])

    assert watch(follow=False) == [ended(1)]
