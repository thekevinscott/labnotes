import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest import mock

from textual.color import Color
from textual.pilot import Pilot
from textual.widgets import Header, Static

from labnotes.runner.start_experiment import ExperimentStart
from labnotes.tui.run_app import RunApp


def planned(at: float) -> dict[str, object]:
    return {
        "event": "planned",
        "title": "exp",
        "runs": [{"run": "r1", "params": {}}],
        "concurrency": 1,
        "at": at,
    }


def concurrency(count: int, at: float) -> dict[str, object]:
    return {"event": "concurrency", "concurrency": count, "at": at}


def background(app: RunApp) -> Color:
    return app.query_one("#concurrency", Static).background_colors[1]


def normal(app: RunApp) -> Color:
    return app.query_one(Header).background_colors[1]


def label(app: RunApp) -> str:
    return str(app.query_one("#concurrency", Static).render())


async def stays_normal(app: RunApp, pilot: Pilot[None], seconds: float) -> None:
    for _ in range(int(seconds * 10)):
        await pilot.pause(0.1)
        assert background(app) == normal(app)


def attached(
    *replayed: dict[str, object],
    scenario: Callable[[RunApp, Pilot[None], Callable[..., None]], Awaitable[None]],
) -> None:
    reporter: list[Callable[[dict[str, object]], None]] = []

    async def attach(report, listen):
        reporter.append(report)
        for event in replayed:
            report(event)
        await asyncio.Event().wait()
        return []

    def send(*events: dict[str, object]) -> None:
        for event in events:
            reporter[0](event)

    async def drive() -> None:
        config = mock.Mock(root=Path.cwd(), experiments="{experiment}", defaults={})
        app = RunApp(
            ExperimentStart(mock.Mock(), attach),
            "exp",
            ("run", "params", "status", "time"),
            config,
        )
        async with app.run_test() as pilot:
            await scenario(app, pilot, send)

    asyncio.run(drive())


def test_first_draw_does_not_flash() -> None:
    async def scenario(app: RunApp, pilot: Pilot[None], send) -> None:
        await stays_normal(app, pilot, 1.0)
        assert "1 at a time" in label(app)

    attached(planned(time.time()), scenario=scenario)


def test_replayed_changes_do_not_flash() -> None:
    old = time.time() - 600

    async def scenario(app: RunApp, pilot: Pilot[None], send) -> None:
        await stays_normal(app, pilot, 1.0)
        assert "2 at a time" in label(app)

    attached(planned(old), concurrency(3, old), concurrency(2, old), scenario=scenario)


def test_live_change_flashes() -> None:
    async def scenario(app: RunApp, pilot: Pilot[None], send) -> None:
        await stays_normal(app, pilot, 0.5)
        send(concurrency(1, time.time()))
        await stays_normal(app, pilot, 0.5)
        send(concurrency(4, time.time()))
        await pilot.pause(0.4)
        assert "4 at a time" in label(app)
        assert background(app) != normal(app)

    attached(planned(time.time() - 600), scenario=scenario)


def test_flash_fades_back_within_about_a_second() -> None:
    async def scenario(app: RunApp, pilot: Pilot[None], send) -> None:
        await pilot.pause(0.5)
        send(concurrency(4, time.time()))
        await pilot.pause(0.4)
        flashed = background(app)
        assert flashed != normal(app)
        await pilot.pause(0.3)
        fading = background(app)
        assert fading not in (flashed, normal(app))
        await pilot.pause(1.0)
        assert background(app) == normal(app)

    attached(planned(time.time() - 600), scenario=scenario)
