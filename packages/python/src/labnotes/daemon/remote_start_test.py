import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.daemon.remote_start import remote_start

CONFIG = mock.Mock(root=Path("/p"))


def message(event: dict[str, object]) -> mock.Mock:
    return mock.Mock(json=mock.Mock(return_value=event))


@pytest.fixture
def daemon() -> Iterator[dict[str, Any]]:
    client = mock.MagicMock()
    client.post = mock.AsyncMock(return_value=mock.Mock(status_code=202))
    response = client.stream.return_value.__aenter__.return_value
    sent: list[dict[str, object]] = [{"event": "connected", "client": 7}]

    async def stream(_: object) -> AsyncIterator[mock.Mock]:
        for event in sent:
            yield message(event)

    with (
        mock.patch(
            "labnotes.daemon.remote_start.ensure_daemon", new=mock.AsyncMock()
        ) as ensure_daemon,
        mock.patch("labnotes.daemon.remote_start.daemon_client") as daemon_client,
        mock.patch(
            "labnotes.daemon.remote_start.httpx2.EventSource", side_effect=stream
        ) as event_source,
    ):
        daemon_client.return_value.__aenter__.return_value = client
        yield {
            "client": client,
            "response": response,
            "sent": sent,
            "ensure_daemon": ensure_daemon,
            "daemon_client": daemon_client,
            "event_source": event_source,
        }


def go(
    experiment_config: Path | None = None,
    report: mock.Mock | None = None,
    listen: mock.Mock | None = None,
    timeout: float | None = None,
) -> list[dict[str, object]]:
    start = remote_start(CONFIG, "exp", experiment_config, 3, timeout)
    return asyncio.run(start(report or mock.Mock(), listen or mock.Mock()))


def test_runs_the_experiment_through_the_daemon(
    tmp_path: Path, daemon: dict[str, Any]
) -> None:
    daemon["sent"].extend(
        [
            {"event": "planned", "experiment": "other"},
            {"event": "planned", "experiment": "abc"},
            {"event": "planned", "experiment": "".join("exp"), "folder": "/r1"},
            {"event": "ended", "experiment": "exp", "exit_code": 0},
            {"event": "done", "experiment": "exp", "error": None},
            {"event": "planned", "experiment": "exp", "folder": "/late"},
        ]
    )
    report = mock.Mock()
    toml = tmp_path / "x.toml"

    results = go(toml, report)

    daemon["ensure_daemon"].assert_awaited_once_with(CONFIG)
    daemon["daemon_client"].assert_called_once_with(Path("/p"))
    daemon["client"].stream.assert_called_once_with("GET", "/events")
    daemon["event_source"].assert_called_once_with(daemon["response"])
    daemon["client"].post.assert_awaited_once_with(
        "/experiments/exp/run",
        json={
            "client": 7,
            "experiment_config": str(toml.resolve()),
            "concurrency": 3,
            "timeout": None,
            "only": None,
            "args": None,
        },
    )
    assert report.call_args_list == [
        mock.call({"event": "planned", "folder": "/r1"}),
        mock.call({"event": "ended", "exit_code": 0}),
    ]
    assert results == [{"event": "ended", "exit_code": 0}]


def test_sends_no_experiment_config_by_default(daemon: dict[str, Any]) -> None:
    daemon["sent"].append({"event": "done", "experiment": "exp", "error": None})

    assert go() == []

    assert daemon["client"].post.call_args.kwargs["json"] == {
        "client": 7,
        "experiment_config": None,
        "concurrency": 3,
        "timeout": None,
        "only": None,
        "args": None,
    }


def test_sends_the_subset_to_run(daemon: dict[str, Any]) -> None:
    daemon["sent"].append({"event": "done", "experiment": "exp", "error": None})

    start = remote_start(CONFIG, "exp", None, 3, None, {"model": "small"})
    asyncio.run(start(mock.Mock(), mock.Mock()))

    assert daemon["client"].post.call_args.kwargs["json"]["only"] == {"model": "small"}


def test_sends_the_args_to_run(daemon: dict[str, Any]) -> None:
    daemon["sent"].append({"event": "done", "experiment": "exp", "error": None})

    start = remote_start(CONFIG, "exp", None, 3, args=["--auth", "api"])
    asyncio.run(start(mock.Mock(), mock.Mock()))

    assert daemon["client"].post.call_args.kwargs["json"]["args"] == ["--auth", "api"]


def test_sends_controls_to_the_daemon(daemon: dict[str, Any]) -> None:
    daemon["sent"].extend(
        [
            {"event": "planned", "experiment": "exp"},
            {"event": "done", "experiment": "exp", "error": None},
        ]
    )
    listen = mock.Mock()

    def press(_: object) -> None:
        controls = listen.call_args.args[0]
        controls.kill("r1")
        controls.finish()

    go(report=mock.Mock(side_effect=press), listen=listen)

    assert daemon["client"].post.await_args_list[1:] == [
        mock.call("/experiments/exp/kill", json={"args": ["r1"]}),
        mock.call("/experiments/exp/finish", json={"args": []}),
    ]


def test_reports_a_refused_start(daemon: dict[str, Any]) -> None:
    daemon["client"].post.return_value = mock.Mock(
        status_code=409, json=mock.Mock(return_value={"error": "exp is running."})
    )
    listen = mock.Mock()

    with pytest.raises(ValueError, match=r"^exp is running\.$"):
        go(listen=listen)

    listen.assert_not_called()


def test_reports_a_session_that_failed(daemon: dict[str, Any]) -> None:
    daemon["sent"].append({"event": "done", "experiment": "exp", "error": "boom"})

    with pytest.raises(ValueError, match="^exp stopped: boom$"):
        go()


def test_reports_a_lost_daemon(daemon: dict[str, Any]) -> None:
    daemon["sent"].append({"event": "planned", "experiment": "exp"})

    with pytest.raises(ValueError, match=r"^Lost the labnotes daemon\.$"):
        go()


def test_reports_a_daemon_that_closes_the_stream_at_once(
    daemon: dict[str, Any],
) -> None:
    daemon["sent"].clear()

    with pytest.raises(ValueError, match=r"^Lost the labnotes daemon\.$"):
        go()

    daemon["client"].post.assert_not_awaited()


def test_names_why_the_daemon_could_not_start(daemon: dict[str, Any]) -> None:
    daemon["ensure_daemon"].side_effect = OSError("AF_UNIX path too long")

    with pytest.raises(
        ValueError, match="^Can't reach the labnotes daemon: AF_UNIX path too long$"
    ):
        go()

    daemon["daemon_client"].assert_not_called()


class Transport(Exception):
    pass


@pytest.fixture
def transport_error() -> Iterator[None]:
    with mock.patch("labnotes.daemon.remote_start.httpx2.TransportError", Transport):
        yield


@pytest.mark.usefixtures("transport_error")
def test_names_why_the_daemon_could_not_be_reached(daemon: dict[str, Any]) -> None:
    daemon["client"].stream.side_effect = Transport("refused")

    with pytest.raises(ValueError, match="^Can't reach the labnotes daemon: refused$"):
        go()


@pytest.mark.usefixtures("transport_error")
def test_names_the_error_type_when_it_has_no_message(daemon: dict[str, Any]) -> None:
    daemon["client"].post.side_effect = Transport()

    with pytest.raises(
        ValueError, match="^Can't reach the labnotes daemon: Transport$"
    ):
        go()


def test_sends_the_timeout(daemon: dict[str, Any]) -> None:
    daemon["sent"].append({"event": "done", "experiment": "exp", "error": None})

    go(timeout=90)

    assert daemon["client"].post.call_args.kwargs["json"]["timeout"] == 90
