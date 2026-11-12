import asyncio
import json
from collections.abc import Callable
from pathlib import Path

from textual.widgets import Tree

from labnotes.models import LabnotesConfig
from labnotes.tui.file_browser import FileBrowser
from labnotes.tui.file_tail import TAIL_BYTES, FileTail
from labnotes.tui.run_app import RunApp


async def until(check: Callable[[], bool], pilot: object) -> None:
    for _ in range(200):
        if check():
            return
        await pilot.pause(0.05)  # type: ignore[attr-defined]
    assert check()


def labels(browser: FileBrowser) -> list[str]:
    tree = browser.query_one(Tree)
    return [str(leaf.label) for run in tree.root.children for leaf in run.children]


def test_file_browser_view_lists_tails_and_follows_run_files(tmp_path: Path) -> None:
    async def drive() -> None:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "alpha/experiment.toml").write_text(
            'command = "echo ok"\ncontinues = false\n'
            '[views]\nfiles = "labnotes.tui.file_browser:FileBrowser"\n'
        )
        run = tmp_path / "alpha/runs/first"
        run.mkdir(parents=True)
        (run / "run.json").write_text(
            json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0})
        )
        (run / "metrics.txt").write_text("step 1\n")
        (run / "big.log").write_bytes(b"x" * (2 * TAIL_BYTES) + b"\nbig end\n")
        (run / "model.pt").write_bytes(b"\x00\x01\x02")
        config = LabnotesConfig(
            tmp_path / ".labnotes.toml",
            tmp_path,
            "{experiment}",
            "{experiment}/files/",
            "{experiment}/runs/{run}",
        )
        waiting = asyncio.Event()

        async def start(report, listen):
            await waiting.wait()
            return []

        app = RunApp(start, "alpha", ("run", "status"), config=config)
        async with app.run_test(size=(120, 30)) as pilot:
            await until(lambda: bool(app.query("#view-2")), pilot)
            await pilot.press("2")
            browser = app.query_one(FileBrowser)
            await until(lambda: "metrics.txt" in labels(browser), pilot)
            assert labels(browser) == ["big.log", "metrics.txt", "model.pt", "run.json"]

            (run / "samples").mkdir()
            (run / "samples/one.txt").write_text("sample\n")
            await until(lambda: "samples/one.txt" in labels(browser), pilot)

            tree = browser.query_one(Tree)
            tail = browser.query_one(FileTail)
            leaves = {str(leaf.label): leaf for leaf in tree.root.children[0].children}
            tree.focus()
            tree.move_cursor(leaves["metrics.txt"])
            await pilot.press("enter")
            await until(lambda: list(tail.lines) == ["step 1", ""], pilot)
            with (run / "metrics.txt").open("a") as file:
                file.write("step 2\n")
            await until(lambda: list(tail.lines) == ["step 1", "step 2", ""], pilot)

            tree.move_cursor(leaves["big.log"])
            await pilot.press("enter")
            await until(lambda: tail.path == run / "big.log", pilot)
            assert tail.lines[0].startswith("[skipped ")
            assert tail.lines[-2] == "big end"

            tree.move_cursor(leaves["model.pt"])
            await pilot.press("enter")
            await until(
                lambda: list(tail.lines)
                == ["model.pt is binary (3 bytes), so it isn't shown."],
                pilot,
            )
            waiting.set()

    asyncio.run(drive())
