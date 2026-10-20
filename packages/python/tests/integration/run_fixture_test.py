import asyncio
import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.runner.param_args import param_args
from labnotes.tui.format_elapsed import format_elapsed
from labnotes.tui.run_app import SPINNER, RunApp

# Shared with the Claude Code pane's tests, so the two views stay alike.
FIXTURE = json.loads(
    (Path(__file__).parents[4] / "skills/labnotes/fixtures/run.json").read_text()
)


def snapshot(app: RunApp) -> dict[str, object]:
    table: Any = app.query_one("#runs")
    rows = []
    for key in table.rows:
        run, params, status, elapsed = table.get_row(key)
        text = str(status)
        rows.append(
            {
                "run": str(run),
                "params": str(params),
                "status": "running" if len(text) == 1 and text in SPINNER else text,
                "statusStyle": str(getattr(status, "style", "") or ""),
                "dim": getattr(run, "style", None) == "dim",
                "time": str(elapsed),
            }
        )
    return {"title": app.title, "concurrency": app.concurrency, "rows": rows}


@pytest.fixture
def skip_ahead() -> Iterator[Callable[[float], None]]:
    # Time keeps flowing for asyncio and Textual; the test only jumps it forward.
    ahead = [0.0]
    real = time.monotonic
    with mock.patch("time.monotonic", lambda: real() + ahead[0]):
        yield lambda seconds: ahead.__setitem__(0, ahead[0] + seconds)


def test_shows_the_recorded_runs_like_the_pane(
    skip_ahead: Callable[[float], None],
) -> None:
    seen: list[dict[str, object]] = []

    async def start(report: Any, listen: Any) -> list[dict[str, object]]:
        for index, event in enumerate(FIXTURE["events"]):
            if index:
                skip_ahead(FIXTURE["step"])
            if event["event"] in ("output", "done"):
                continue
            report({k: v for k, v in event.items() if k != "experiment"})
            app.tick()
            seen.append({"after": index + 1, **snapshot(app)})
        return []

    async def drive() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()

    app = RunApp(start, "exp")

    asyncio.run(drive())
    assert seen == FIXTURE["checkpoints"]


@pytest.mark.parametrize(("params", "args"), FIXTURE["params"])
def test_writes_params_like_the_pane(params: dict[str, object], args: str) -> None:
    assert " ".join(param_args(params)) == args


@pytest.mark.parametrize(("seconds", "text"), FIXTURE["elapsed"])
def test_writes_elapsed_time_like_the_pane(seconds: float, text: str) -> None:
    assert format_elapsed(seconds) == text
