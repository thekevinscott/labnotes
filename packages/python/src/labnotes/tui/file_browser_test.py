import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import Tree

from labnotes.tui.file_browser import FileBrowser
from labnotes.tui.file_tail import FileTail
from labnotes.view.changed import Changed
from labnotes.view.experiment import Experiment


class Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield FileBrowser()


def drive(check: Callable[[Any, FileBrowser], Awaitable[None]]) -> None:
    async def run() -> None:
        async with Harness().run_test() as pilot:
            await check(pilot, pilot.app.query_one(FileBrowser))

    asyncio.run(run())


def experiment(
    root: Path, folders: tuple[str, ...], files: tuple[str, ...]
) -> Experiment:
    runs = tuple({"id": Path(folder).name, "folder": folder} for folder in folders)
    return Experiment(root, "alpha", runs, files=files)


def shown(browser: FileBrowser) -> list[tuple[str, list[str]]]:
    tree = browser.query_one(Tree)
    return [
        (str(run.label), [str(leaf.label) for leaf in run.children])
        for run in tree.root.children
    ]


async def deliver(pilot: Any, browser: FileBrowser, message: Changed) -> None:
    browser.post_message(message)
    await pilot.pause()


def test_lists_each_runs_files_under_it(tmp_path: Path) -> None:
    async def check(pilot: Any, browser: FileBrowser) -> None:
        files = (
            "alpha/runs/a/metrics.txt",
            "alpha/runs/a/out/sample.txt",
            "alpha/runs/b/stdout.log",
            "alpha/setup/stdout.log",
        )
        await deliver(
            pilot,
            browser,
            Changed(experiment(tmp_path, ("alpha/runs/a", "alpha/runs/b"), files)),
        )
        assert shown(browser) == [
            ("a", ["metrics.txt", "out/sample.txt"]),
            ("b", ["stdout.log"]),
        ]
        assert all(run.is_expanded for run in browser.query_one(Tree).root.children)

    drive(check)


def test_keeps_the_list_current(tmp_path: Path) -> None:
    async def check(pilot: Any, browser: FileBrowser) -> None:
        first = experiment(
            tmp_path, ("alpha/runs/a", "alpha/runs/b"), ("alpha/runs/a/old.txt",)
        )
        await deliver(pilot, browser, Changed(first))
        kept = browser.query_one(Tree).root.children[0]
        later = experiment(
            tmp_path,
            ("alpha/runs/a", "alpha/runs/c"),
            ("alpha/runs/a/new.txt", "alpha/runs/c/stdout.log"),
        )
        await deliver(pilot, browser, Changed(later))
        assert shown(browser) == [("a", ["new.txt"]), ("c", ["stdout.log"])]
        assert browser.query_one(Tree).root.children[0] is kept
        await deliver(pilot, browser, Changed(None))
        assert shown(browser) == []
        await deliver(pilot, browser, Changed(later))
        assert shown(browser) == [("a", ["new.txt"]), ("c", ["stdout.log"])]

    drive(check)


def test_drops_a_runs_files_with_the_run(tmp_path: Path) -> None:
    async def check(pilot: Any, browser: FileBrowser) -> None:
        both = experiment(
            tmp_path,
            ("alpha/runs/a", "alpha/runs/b"),
            ("alpha/runs/a/x.txt", "alpha/runs/b/y.txt"),
        )
        await deliver(pilot, browser, Changed(both))
        only = experiment(tmp_path, ("alpha/runs/a",), both.files)
        await deliver(pilot, browser, Changed(only))
        assert shown(browser) == [("a", ["x.txt"])]
        await deliver(pilot, browser, Changed(both))
        assert shown(browser) == [("a", ["x.txt"]), ("b", ["y.txt"])]

    drive(check)


def test_selecting_a_file_tails_it_and_follows_its_changes(tmp_path: Path) -> None:
    run = tmp_path / "alpha/runs/a"
    run.mkdir(parents=True)
    (run / "metrics.txt").write_text("step 1\n")
    (run / "other.txt").write_text("other\n")
    files = ("alpha/runs/a/metrics.txt", "alpha/runs/a/other.txt")
    shot = experiment(tmp_path, ("alpha/runs/a",), files)

    async def check(pilot: Any, browser: FileBrowser) -> None:
        await deliver(pilot, browser, Changed(shot))
        tail = browser.query_one(FileTail)
        tree = browser.query_one(Tree)
        tree.focus()
        tree.move_cursor(tree.root.children[0])
        await pilot.press("enter", "enter")
        assert tail.path is None
        tree.move_cursor(tree.root.children[0].children[0])
        await pilot.press("enter")
        await pilot.pause()
        assert tail.path == run / "metrics.txt"
        assert list(tail.lines) == ["step 1", ""]
        with (run / "metrics.txt").open("a") as file:
            file.write("step 2\n")
        with (run / "other.txt").open("a") as file:
            file.write("more\n")
        await deliver(
            pilot, browser, Changed(shot, frozenset({"alpha/runs/a/other.txt"}))
        )
        assert list(tail.lines) == ["step 1", ""]
        await deliver(
            pilot, browser, Changed(shot, frozenset({"alpha/runs/a/metrics.txt"}))
        )
        assert list(tail.lines) == ["step 1", "step 2", ""]

    drive(check)
