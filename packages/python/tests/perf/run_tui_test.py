import asyncio
import time
from pathlib import Path

import pytest

from labnotes.tui.config import RUN_COLUMNS
from labnotes.tui.run_app import RunApp

COLORED_LINE = b"\x1b[31mred output\x1b[0m " * 20 + b"\n"


def write_log(log: Path, log_shape: str) -> None:
    if log_shape == "colored_lines":
        log.write_bytes(COLORED_LINE * 100_000)
    else:
        log.write_bytes(b"x" * (42 * 1024 * 1024))


@pytest.mark.parametrize("log_shape", ["colored_lines", "one_huge_line"])
def test_overview_timer_keeps_ticking_through_large_run_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, log_shape: str
) -> None:
    run_folder = tmp_path / "run-1"
    run_folder.mkdir()
    write_log(run_folder / "stdout.log", log_shape)
    ticks: list[float] = []

    async def drive() -> None:
        keep_running = asyncio.Event()

        async def start(report, listen):
            report(
                {
                    "event": "planned",
                    "title": "perf",
                    "concurrency": 1,
                    "runs": [
                        {"run": "run-1", "params": {}},
                        {"run": "run-2", "params": {}},
                    ],
                }
            )
            report(
                {
                    "event": "started",
                    "run": "run-1",
                    "params": {},
                    "folder": run_folder,
                }
            )
            await keep_running.wait()
            return []

        app = RunApp(start, "perf", RUN_COLUMNS)
        original_tick = app.body.tick

        def timed_tick() -> None:
            ticks.append(time.monotonic())
            original_tick()

        monkeypatch.setattr(app.body, "tick", timed_tick)

        async def wait_for_ticks(count: int) -> None:
            async def wait() -> None:
                while len(ticks) < count:
                    await asyncio.sleep(0.05)

            await asyncio.wait_for(wait(), timeout=30)

        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await wait_for_ticks(2)
                await pilot.press("enter")
                assert app.body.viewing == "run-1"
                await wait_for_ticks(4)
                await pilot.press("escape")
                assert app.body.viewing is None
                await wait_for_ticks(6)
        finally:
            keep_running.set()

    asyncio.run(drive())

    gaps = [later - earlier for earlier, later in zip(ticks, ticks[1:])]
    assert gaps and max(gaps) < 3.0, f"overview timer paused for {max(gaps):.1f}s"
