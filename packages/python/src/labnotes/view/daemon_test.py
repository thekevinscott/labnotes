import asyncio
from pathlib import Path
from typing import Any
from unittest import mock

from labnotes.view import daemon
from labnotes.view.daemon import Daemon


def test_follow_reads_a_route_from_this_experiments_daemon() -> None:
    config = mock.Mock(root=Path("/p"))
    ensure = mock.AsyncMock()
    seen: list[tuple[Any, ...]] = []

    async def follow_route(*args: Any) -> Any:
        seen.append(args)
        yield "state", [{"name": "stdout.log"}]

    async def collect() -> list[tuple[str, Any]]:
        return [
            event async for event in Daemon(config, "alpha", ensure).follow("/runs")
        ]

    with mock.patch("labnotes.view.daemon.follow_route", follow_route):
        events = asyncio.run(collect())

    assert events == [("state", [{"name": "stdout.log"}])]
    assert seen == [(config, "alpha", "/runs", ensure)]


def test_ensures_a_daemon_by_default() -> None:
    assert Daemon(mock.Mock(), "alpha").ensure is daemon.ensure_daemon
