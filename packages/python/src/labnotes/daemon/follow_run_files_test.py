import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest import mock

from labnotes.daemon.follow_run_files import RETRY_SECONDS, follow_run_files

MODULE = "labnotes.daemon.follow_run_files"


def attempts(*replies: list[tuple[str, Any]] | Exception) -> mock.Mock:
    left = list(replies)

    async def follow(*_: object) -> AsyncIterator[tuple[str, Any]]:
        reply = left.pop(0)
        if isinstance(reply, Exception):
            raise reply
        for event in reply:
            yield event

    return mock.Mock(side_effect=follow)


async def take(follow: mock.Mock, count: int, run: str = "r1") -> list[Any]:
    found: list[Any] = []
    ensure = mock.AsyncMock()
    with (
        mock.patch(f"{MODULE}.follow_route", new=follow),
        mock.patch(f"{MODULE}.asyncio.sleep", new=mock.AsyncMock()) as sleep,
    ):
        stream = follow_run_files(mock.sentinel.config, "exp", run, ensure)
        async for event in stream:
            found.append(event)
            if len(found) == count:
                break
        await stream.aclose()
    return [found, sleep, ensure]


def test_follows_the_runs_files_route() -> None:
    follow = attempts([("state", [{"name": "a.log"}]), ("file", {"name": "b"})])
    found, sleep, ensure = asyncio.run(take(follow, 2))
    assert found == [("state", [{"name": "a.log"}]), ("file", {"name": "b"})]
    follow.assert_called_once_with(
        mock.sentinel.config, "exp", "/runs/r1/files", ensure
    )
    sleep.assert_not_awaited()


def test_quotes_the_run_but_keeps_its_slashes() -> None:
    follow = attempts([("state", [])])
    asyncio.run(take(follow, 1, run="grid/a b?#"))
    assert follow.call_args.args[2] == "/runs/grid/a%20b%3F%23/files"


def test_waits_for_the_daemon_to_know_a_new_run() -> None:
    follow = attempts(ValueError("Not found"), [("state", [{"name": "a.log"}])])
    found, sleep, _ = asyncio.run(take(follow, 1))
    assert found == [("state", [{"name": "a.log"}])]
    assert follow.call_count == 2
    sleep.assert_awaited_once_with(RETRY_SECONDS)


def test_starts_over_when_a_stream_ends() -> None:
    follow = attempts([("state", [])], [("state", [{"name": "a.log"}])])
    found, sleep, _ = asyncio.run(take(follow, 2))
    assert found == [("state", []), ("state", [{"name": "a.log"}])]
    sleep.assert_awaited_once_with(RETRY_SECONDS)


def test_retries_promptly() -> None:
    assert RETRY_SECONDS == 0.5
