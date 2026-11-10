import asyncio
import threading
from collections.abc import Callable
from unittest import mock

import pytest

from labnotes.daemon.request_start import request_start


def run(command: Callable[..., dict[str, object]]) -> tuple[object, list[str]]:
    steps: list[str] = []

    async def ensure(config: object, name: str, progress: Callable[[str], None]):
        progress("Starting daemon")

    with (
        mock.patch("labnotes.daemon.request_start.ensure_daemon", new=ensure),
        mock.patch("labnotes.daemon.request_start.command", side_effect=command),
    ):
        reply = asyncio.run(
            request_start(
                mock.sentinel.config, "exp", {"command": "start"}, steps.append
            )
        )
    return reply, steps


def test_relays_steps_in_order_and_returns_the_accepted_reply() -> None:
    def command(config, name, message, progress):
        assert (config, name, message) == (
            mock.sentinel.config,
            "exp",
            {"command": "start"},
        )
        progress("Snapshotting repo")
        return {"ok": True, "journal": "j.jsonl"}

    reply, steps = run(command)
    assert reply == {"ok": True, "journal": "j.jsonl"}
    assert steps == ["Starting daemon", "Connecting to daemon", "Snapshotting repo"]


def test_sends_from_a_daemon_thread() -> None:
    def command(config, name, message, progress):
        assert threading.current_thread().daemon
        return {"ok": True}

    assert run(command)[0] == {"ok": True}


def test_raises_the_daemon_rejection() -> None:
    with pytest.raises(ValueError, match="already running"):
        run(lambda *args: {"ok": False, "error": "already running"})


def test_names_a_rejection_without_an_error() -> None:
    with pytest.raises(ValueError, match="Daemon rejected start"):
        run(lambda *args: {"ok": False})


def test_raises_a_lost_daemon() -> None:
    def command(*args: object) -> dict[str, object]:
        raise ValueError("Daemon for exp closed without a reply.")

    with pytest.raises(ValueError, match="closed without a reply"):
        run(command)


def test_late_news_after_the_loop_closes_is_dropped() -> None:
    release = threading.Event()
    finished = threading.Event()

    def command(config, name, message, progress):
        release.wait(5)
        progress("Starting run")
        finished.set()
        return {"ok": True}

    async def ensure(*args: object) -> None:
        return None

    async def abandon() -> None:
        started = asyncio.ensure_future(
            request_start(mock.sentinel.config, "exp", {}, lambda step: None)
        )
        await asyncio.sleep(0.05)
        started.cancel()

    with (
        mock.patch("labnotes.daemon.request_start.ensure_daemon", new=ensure),
        mock.patch("labnotes.daemon.request_start.command", side_effect=command),
    ):
        asyncio.run(abandon())
        release.set()
        assert finished.wait(5)


def test_a_reply_after_cancelling_is_ignored() -> None:
    release = threading.Event()

    def command(config, name, message, progress):
        release.wait(5)
        return {"ok": True}

    async def ensure(*args: object) -> None:
        return None

    async def abandon() -> None:
        started = asyncio.ensure_future(
            request_start(mock.sentinel.config, "exp", {}, lambda step: None)
        )
        await asyncio.sleep(0.05)
        started.cancel()
        release.set()
        await asyncio.sleep(0.2)
        assert started.cancelled()

    with (
        mock.patch("labnotes.daemon.request_start.ensure_daemon", new=ensure),
        mock.patch("labnotes.daemon.request_start.command", side_effect=command),
    ):
        asyncio.run(abandon())
