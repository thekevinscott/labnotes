import asyncio
from collections.abc import Callable, Iterator
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.run_app import RunApp

Report = Callable[[dict[str, object]], None]
Listen = Callable[[Callable[[], None]], None]


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.run_app.param_args",
            side_effect=lambda params: ["--m", params["m"]],
        ),
        mock.patch(
            "labnotes.tui.run_app.describe_event",
            side_effect=lambda event: f"said {event['event']}",
        ),
        mock.patch(
            "labnotes.tui.run_app.format_elapsed",
            side_effect=lambda seconds: f"{seconds:g}s",
        ),
        mock.patch("labnotes.tui.run_app.time") as time,
    ):
        time.monotonic.return_value = 100.0
        yield {"time": time}


def rows(app: RunApp) -> list[list[object]]:
    table: Any = app.query_one("#runs")
    return [table.get_row(key) for key in table.rows]


def status(app: RunApp) -> str:
    widget: Any = app.query_one("#status")
    return str(widget.content)


def test_shows_each_run_and_the_outcome(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report({"event": "planned"})
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        report({"event": "started", "run": "r2", "params": {"m": "b"}})
        collaborators["time"].monotonic.return_value = 103.0
        report({"event": "ended", "run": "r1", "exit_code": 0, "error": None})
        report({"event": "ended", "run": "r2", "exit_code": None, "error": "boom"})
        return [{"exit_code": 0}, {"exit_code": None}]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.title == "exp"
            assert rows(app) == [
                ["r1", "--m a", "exited 0", "3s"],
                ["r2", "--m b", "boom", "3s"],
            ]
            assert status(app) == "1 passed, 1 failed. q to quit."
            assert app.results == [{"exit_code": 0}, {"exit_code": None}]
            await pilot.press("q")
            assert not app.is_running

    asyncio.run(drive())


def test_shows_other_events_as_status() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report({"event": "stopping"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert status(app) == "said stopping"

    asyncio.run(drive())


def test_ticks_the_time_of_running_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            collaborators["time"].monotonic.return_value = 105.0
            app.tick()
            assert rows(app) == [["r1", "--m a", "running", "5s"]]

    asyncio.run(drive())


def test_ctrl_c_interrupts_the_runs_until_they_finish() -> None:
    interrupt = mock.Mock()
    finish = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(interrupt)
        await finish.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.press("ctrl+c")
            assert interrupt.call_count == 2
            assert app.is_running
            finish.set()
            await pilot.pause()
            await pilot.press("ctrl+c")
            assert not app.is_running
            assert interrupt.call_count == 2

    asyncio.run(drive())


def test_waits_for_runs_before_quitting() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.press("q")
            assert app.is_running
            assert status(app) == "Runs are still going. Ctrl-C stops them."

    asyncio.run(drive())
