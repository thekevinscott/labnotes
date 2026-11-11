import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest import mock

from textual.color import Color
from textual.pilot import Pilot
from textual.widgets import Header, Static

from labnotes.runner.run_state import RunState
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


def write(path: Path, *events: dict[str, object]) -> None:
    with path.open("a") as file:
        for event in events:
            file.write(json.dumps(event) + "\n")


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
    journal: Path, scenario: Callable[[RunApp, Pilot[None]], Awaitable[None]]
) -> None:
    async def attach(report, listen):
        report({"event": "wake up"})
        await asyncio.Event().wait()
        return []

    async def drive() -> None:
        config = mock.Mock(root=journal.parent, experiments="{experiment}", defaults={})
        app = RunApp(
            ExperimentStart(RunState(journal), attach),
            "exp",
            ("run", "params", "status", "time"),
            config,
        )
        async with app.run_test() as pilot:
            await scenario(app, pilot)

    asyncio.run(drive())


def test_first_draw_does_not_flash(tmp_path: Path) -> None:
    journal = tmp_path / "run.jsonl"
    write(journal, planned(time.time()))

    async def scenario(app: RunApp, pilot: Pilot[None]) -> None:
        await stays_normal(app, pilot, 1.0)
        assert "1 at a time" in label(app)

    attached(journal, scenario)


def test_journal_replay_does_not_flash(tmp_path: Path) -> None:
    journal = tmp_path / "run.jsonl"
    old = time.time() - 600
    write(journal, planned(old), concurrency(3, old), concurrency(2, old))

    async def scenario(app: RunApp, pilot: Pilot[None]) -> None:
        await stays_normal(app, pilot, 1.0)
        assert "2 at a time" in label(app)

    attached(journal, scenario)


def test_live_change_flashes(tmp_path: Path) -> None:
    journal = tmp_path / "run.jsonl"
    write(journal, planned(time.time() - 600))

    async def scenario(app: RunApp, pilot: Pilot[None]) -> None:
        await stays_normal(app, pilot, 0.5)
        write(journal, concurrency(1, time.time()))
        await stays_normal(app, pilot, 0.5)
        write(journal, concurrency(4, time.time()))
        await pilot.pause(0.4)
        assert "4 at a time" in label(app)
        assert background(app) != normal(app)

    attached(journal, scenario)


def test_flash_fades_back_within_about_a_second(tmp_path: Path) -> None:
    journal = tmp_path / "run.jsonl"
    write(journal, planned(time.time() - 600))

    async def scenario(app: RunApp, pilot: Pilot[None]) -> None:
        await pilot.pause(0.5)
        write(journal, concurrency(4, time.time()))
        await pilot.pause(0.4)
        flashed = background(app)
        assert flashed != normal(app)
        await pilot.pause(0.3)
        fading = background(app)
        assert fading not in (flashed, normal(app))
        await pilot.pause(1.0)
        assert background(app) == normal(app)

    attached(journal, scenario)
