import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import DataTable, Log, Tab

from labnotes.tui.run_output import RunOutput


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output", files=True)


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
    for _ in range(200):
        app.query_one(RunOutput).follow(folder)
        await pilot.pause(0.05)
        if done():
            return
    raise AssertionError("timed out")


def browse(folder: Path, check: Callable[[Pilot[None], Host], Awaitable[None]]) -> None:
    async def drive() -> None:
        app = Host()
        async with app.run_test(size=(120, 30)) as pilot:
            output = app.query_one(RunOutput)
            output.show("files")
            output.focus()
            await check(pilot, app)

    asyncio.run(drive())


def test_lists_a_runs_files_and_keeps_the_list_current(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("hi\n")
    (tmp_path / "ckpt").mkdir()
    (tmp_path / "ckpt/epoch-1.pt").write_bytes(b"\0" * 10)

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, tmp_path, lambda: label(app) == "files (2)")
        assert listed(app) == ["ckpt/epoch-1.pt", "stdout.log"]
        (tmp_path / "metrics.csv").write_text("loss\n")
        await until(pilot, app, tmp_path, lambda: label(app) == "files (3)")
        assert listed(app) == ["ckpt/epoch-1.pt", "metrics.csv", "stdout.log"]

    browse(tmp_path, check)


def test_selecting_a_file_tails_it_and_follows_new_lines(tmp_path: Path) -> None:
    progress = tmp_path / "a-progress.log"
    progress.write_text("".join(f"step {n}\n" for n in range(20000)))
    (tmp_path / "stdout.log").write_text("")

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, tmp_path, lambda: len(listed(app)) == 2)
        await pilot.press("enter")
        await until(pilot, app, tmp_path, lambda: "step 19999" in tail(app))
        assert "step 0" not in tail(app)
        with progress.open("a") as file:
            file.write("step 20000\n")
        await until(pilot, app, tmp_path, lambda: "step 20000" in tail(app))

    browse(tmp_path, check)


def test_a_binary_file_is_named_not_dumped(tmp_path: Path) -> None:
    (tmp_path / "plot.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00" + bytes(range(256)))

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, tmp_path, lambda: len(listed(app)) == 1)
        await pilot.press("enter")
        await until(pilot, app, tmp_path, lambda: bool(tail(app)))
        assert tail(app) == ["plot.png is binary (265 bytes), not shown."]

    browse(tmp_path, check)


def test_a_large_file_opens_without_reading_all_of_it(tmp_path: Path) -> None:
    big = tmp_path / "big.log"
    line = b"x" * 99 + b"\n"
    with big.open("wb") as file:
        for _ in range(64):
            file.write(line * 10_000)
        file.write(b"the end\n")

    async def check(pilot: Pilot[None], app: Host) -> None:
        await until(pilot, app, tmp_path, lambda: len(listed(app)) == 1)
        began = time.monotonic()
        await pilot.press("enter")
        await until(pilot, app, tmp_path, lambda: "the end" in tail(app))
        assert time.monotonic() - began < 5
        assert len(tail(app)) < 1000

    browse(tmp_path, check)
