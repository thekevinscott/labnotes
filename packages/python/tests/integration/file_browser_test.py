import asyncio
import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import psutil
import pytest
from textual.pilot import Pilot
from textual.widgets import DataTable, Log

from labnotes.models import LabnotesConfig
from labnotes.tui.run_app import RunApp

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256))


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": folder}):
            yield Path(folder)


def stop_daemons(root: Path) -> None:
    config = str(root / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
    ]
    for process in owners:
        process.terminate()
    psutil.wait_procs(owners, timeout=15)


async def until(pilot: Pilot[None], check: Callable[[], bool], what: str) -> None:
    for _ in range(400):
        if check():
            return
        await pilot.pause(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def test_file_browser_lists_the_open_runs_files_and_tails_the_selected_one(
    tmp_path: Path, runtime: Path
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha/experiment.toml").write_text(
        'command = "echo ok"\ncontinues = false\n'
        '[views]\nfiles = "labnotes.tui.file_browser:FileBrowser"\n'
    )
    run = tmp_path / "alpha/runs/first"
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"created": "2026-11-16T00:00:00Z"}))
    (run / "stdout.log").write_text("one\ntwo\n")
    (run / "plot.png").write_bytes(PNG)
    with (run / "big.log").open("w") as big:
        for number in range(400_000):
            big.write(f"big line {number}\n")
    config = LabnotesConfig(
        tmp_path / ".labnotes.toml",
        tmp_path,
        "{experiment}",
        "{experiment}/files/",
        "{experiment}/runs/{run}",
    )

    async def drive() -> None:
        waiting = asyncio.Event()

        async def start(report, listen):  # type: ignore[no-untyped-def]
            report(
                {
                    "event": "planned",
                    "title": "alpha",
                    "runs": [{"run": "first", "params": {}}],
                    "concurrency": 1,
                }
            )
            await waiting.wait()
            return []

        app = RunApp(start, "alpha", ("run", "status"), config=config)
        async with app.run_test(size=(160, 40)) as pilot:
            await until(pilot, lambda: bool(app.query("#view-2 #files")), "the view")
            await pilot.press("2")
            table = app.query_one("#view-2 #files", DataTable)
            log = app.query_one("#view-2 #tail", Log)

            def names() -> list[str]:
                return [str(table.get_row(key)[0]) for key in table.rows]

            await until(
                pilot,
                lambda: names() == ["big.log", "plot.png", "run.json", "stdout.log"],
                "the run's files",
            )
            (run / "metrics.jsonl").write_text('{"loss": 1}\n')
            await until(pilot, lambda: "metrics.jsonl" in names(), "a new file")

            async def select(name: str) -> None:
                table.focus()
                table.move_cursor(row=names().index(name))
                await pilot.press("enter")

            await select("stdout.log")
            await until(pilot, lambda: list(log.lines) == ["one", "two"], "the tail")
            with (run / "stdout.log").open("a") as out:
                out.write("three\n")
            await until(
                pilot, lambda: list(log.lines) == ["one", "two", "three"], "a new line"
            )

            await select("plot.png")
            await until(
                pilot,
                lambda: list(log.lines)
                == ["Binary file (image/png, 272 bytes), not shown."],
                "the binary summary",
            )

            await select("big.log")
            await until(
                pilot,
                lambda: bool(log.lines) and log.lines[-1] == "big line 399999",
                "the big file's tail",
            )
            assert len(log.lines) < 10_000
            waiting.set()

    try:
        asyncio.run(drive())
    finally:
        stop_daemons(tmp_path)
