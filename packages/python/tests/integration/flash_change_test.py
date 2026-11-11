import asyncio
import json
import time
from pathlib import Path
from unittest import mock

from textual.color import Color
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


def write(path: Path, *events: dict[str, object]) -> None:
    with path.open("a") as file:
        for event in events:
            file.write(json.dumps(event) + "\n")


def background(app: RunApp) -> Color:
    return app.query_one("#concurrency", Static).background_colors[1]


def normal(app: RunApp) -> Color:
    return app.query_one(Header).background_colors[1]


def test_concurrency_flashes_only_on_live_changes(tmp_path: Path) -> None:
    journal = tmp_path / "run.jsonl"
    old = time.time() - 600
    write(journal, planned(old), {"event": "concurrency", "concurrency": 3, "at": old})

    async def attach(report, listen):
        report({"event": "wake up"})
        await asyncio.Event().wait()
        return []

    async def scenario() -> None:
        config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
        app = RunApp(
            ExperimentStart(RunState(journal), attach),
            "exp",
            ("run", "params", "status", "time"),
            config,
        )
        async with app.run_test() as pilot:
            for _ in range(10):
                await pilot.pause(0.1)
                assert background(app) == normal(app)
            label = app.query_one("#concurrency", Static)
            assert "3 at a time" in str(label.render())

            write(
                journal, {"event": "concurrency", "concurrency": 3, "at": time.time()}
            )
            for _ in range(5):
                await pilot.pause(0.1)
                assert background(app) == normal(app)

            write(
                journal, {"event": "concurrency", "concurrency": 4, "at": time.time()}
            )
            await pilot.pause(0.4)
            assert "4 at a time" in str(label.render())
            assert background(app) != normal(app)
            await pilot.pause(1.5)
            assert background(app) == normal(app)

    asyncio.run(scenario())
