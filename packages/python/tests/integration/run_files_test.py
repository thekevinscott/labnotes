import asyncio
import json
import os
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import DataTable, Log, Tab

from labnotes.daemon.follow_run_files import follow_run_files
from labnotes.read_config import read_config
from labnotes.tui.run_output import RunOutput

RUN = "20261118-000001-quiet-pond"


class Host(App[None]):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.config = read_config(root / ".labnotes.toml")

    def compose(self) -> ComposeResult:
        yield RunOutput(id="output", files=True)

    def run_files(self, run: str) -> AsyncIterator[tuple[str, Any]]:
        return follow_run_files(self.config, "exp", run)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text('continues = false\ncommand = "true"\n')
    return root


@pytest.fixture
def folder(root: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    folder = root / "exp/runs" / RUN
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(
        json.dumps({"params": {}, "created": "2026-11-18T00:00:01Z"})
    )
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        monkeypatch.setenv("XDG_RUNTIME_DIR", runtime)
        process = subprocess.Popen(
            [
                str(Path(sys.executable).parent / "labnotes"),
                "-c",
                str(root / ".labnotes.toml"),
                "daemon",
                "exp",
            ],
            cwd=root,
            env={**os.environ, "XDG_RUNTIME_DIR": runtime},
            stdout=subprocess.DEVNULL,
        )
        try:
            for _ in range(200):
                if list(Path(runtime).glob("labnotes/*.sock")):
                    break
                time.sleep(0.05)
            yield folder
        finally:
            process.terminate()
            process.wait(timeout=15)


def listed(app: Host) -> list[str]:
    table = app.query_one("#file-list", DataTable)
    return [str(key.value) for key in table.rows]


def label(app: Host) -> str:
    return str(app.query_one("#files-tab", Tab).label_text)


def tail(app: Host) -> list[str]:
    log = app.query_one(Log)
    return [str(line) for line in log.lines]


async def until(
    pilot: Pilot[None], app: Host, folder: Path, done: Callable[[], bool]
) -> None:
    for _ in range(400):
        app.query_one(RunOutput).follow(folder, RUN)
        await pilot.pause(0.05)
        if done():
            return
    raise AssertionError("timed out")


def browse(folder: Path, check: Callable[[Pilot[None], Host], Awaitable[None]]) -> None:
    async def drive() -> None:
        app = Host(folder.parents[2])
        async with app.run_test(size=(120, 30)) as pilot:
            output = app.query_one(RunOutput)
            output.show("files")
            output.focus()
            await check(pilot, app)

    asyncio.run(drive())


def test_lists_a_runs_files_and_keeps_the_list_current(folder: Path) -> None:
    (folder / "stdout.log").write_text("hi\n")
    (folder / "ckpt").mkdir()
    (folder / "ckpt/epoch-1.pt").write_bytes(b"\0" * 10)

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, folder, lambda: label(app) == "files (3)")
        assert listed(app) == ["ckpt/epoch-1.pt", "run.json", "stdout.log"]
        (folder / "metrics.csv").write_text("loss\n")
        await until(pilot, app, folder, lambda: label(app) == "files (4)")
        assert listed(app) == [
            "ckpt/epoch-1.pt",
            "metrics.csv",
            "run.json",
            "stdout.log",
        ]
        (folder / "stdout.log").unlink()
        await until(pilot, app, folder, lambda: label(app) == "files (3)")
        assert listed(app) == ["ckpt/epoch-1.pt", "metrics.csv", "run.json"]

    browse(folder, check)


def test_selecting_a_file_tails_it_and_follows_new_lines(folder: Path) -> None:
    progress = folder / "a-progress.log"
    progress.write_text("".join(f"step {n}\n" for n in range(20000)))
    (folder / "stdout.log").write_text("")

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, folder, lambda: len(listed(app)) == 3)
        await pilot.press("enter")
        await until(pilot, app, folder, lambda: "step 19999" in tail(app))
        assert "step 0" not in tail(app)
        with progress.open("a") as file:
            file.write("step 20000\n")
        await until(pilot, app, folder, lambda: "step 20000" in tail(app))

    browse(folder, check)


def test_a_binary_file_is_named_not_dumped(folder: Path) -> None:
    (folder / "plot.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00" + bytes(range(256)))

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, folder, lambda: len(listed(app)) == 2)
        await pilot.press("enter")
        await until(pilot, app, folder, lambda: bool(tail(app)))
        assert tail(app) == ["plot.png is binary (265 bytes), not shown."]

    browse(folder, check)


def test_a_large_file_opens_without_reading_all_of_it(folder: Path) -> None:
    big = folder / "big.log"
    line = b"x" * 99 + b"\n"
    with big.open("wb") as file:
        for _ in range(64):
            file.write(line * 10_000)
        file.write(b"the end\n")

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, folder, lambda: len(listed(app)) == 2)
        began = time.monotonic()
        await pilot.press("enter")
        await until(pilot, app, folder, lambda: "the end" in tail(app))
        assert time.monotonic() - began < 5
        assert len(tail(app)) < 1000

    browse(folder, check)
