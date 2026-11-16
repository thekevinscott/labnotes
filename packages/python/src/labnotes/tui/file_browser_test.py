import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import DataTable, Log, Static

from labnotes.tui.file_browser import FileBrowser
from labnotes.view.changed import Changed
from labnotes.view.experiment import Experiment
from labnotes.view.selected import Selected

MISSING = object()


class FakeDaemon:
    def __init__(self) -> None:
        self.routes: dict[str, asyncio.Queue[Any]] = defaultdict(asyncio.Queue)
        self.followed: list[str] = []
        self.open: set[str] = set()

    def send(self, route: str, kind: str, data: Any) -> None:
        self.routes[route].put_nowait((kind, data))

    def reject(self, route: str) -> None:
        self.routes[route].put_nowait(MISSING)

    async def follow(self, route: str) -> AsyncIterator[tuple[str, Any]]:
        self.followed.append(route)
        self.open.add(route)
        try:
            while True:
                event = await self.routes[route].get()
                if event is MISSING:
                    raise ValueError("Not found")
                yield event
        finally:
            self.open.discard(route)


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield FileBrowser()


def experiment(*runs: str) -> Experiment:
    return Experiment(
        Path("/p"),
        "alpha",
        tuple({"id": run, "folder": f"alpha/runs/{run}"} for run in runs),
    )


def browse(
    test: Callable[[Pilot[None], FileBrowser, FakeDaemon], Awaitable[None]],
) -> None:
    async def drive() -> None:
        daemon = FakeDaemon()
        app = Host()
        async with app.run_test() as pilot:
            browser = app.query_one(FileBrowser)
            await test(pilot, browser, daemon)

    asyncio.run(drive())


async def settle(pilot: Pilot[None]) -> None:
    for _ in range(3):
        await pilot.pause()


def names(browser: FileBrowser) -> list[str]:
    table = browser.query_one("#files", DataTable)
    return [str(table.get_row(key)[0]) for key in table.rows]


def sizes(browser: FileBrowser) -> list[str]:
    table = browser.query_one("#files", DataTable)
    return [str(table.get_row(key)[1]) for key in table.rows]


def tail(browser: FileBrowser) -> list[str]:
    return list(browser.query_one("#tail", Log).lines)


def title(browser: FileBrowser, name: str) -> str:
    return str(browser.query_one(name, Static).content)


def test_asks_for_a_run_until_one_is_selected() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        browser.post_message(Changed(experiment("a"), daemon=daemon))  # type: ignore[arg-type]
        await settle(pilot)
        assert "Select a run" in title(browser, "#files-title")
        assert daemon.followed == []

    browse(test)


def test_lists_the_selected_runs_files_and_keeps_them_current() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        browser.post_message(Selected("a"))
        browser.post_message(Changed(experiment("a"), daemon=daemon))  # type: ignore[arg-type]
        await settle(pilot)
        assert daemon.followed == ["/runs/a/files"]
        assert "a" in title(browser, "#files-title")
        daemon.send(
            "/runs/a/files",
            "state",
            [
                {"name": "run.json", "size": 10, "mtime": "t"},
                {"name": "stdout.log", "size": 2000, "mtime": "t"},
            ],
        )
        await settle(pilot)
        assert names(browser) == ["run.json", "stdout.log"]
        assert sizes(browser) == ["10 bytes", "2.0 kB"]
        daemon.send(
            "/runs/a/files", "file", {"name": "ckpt/model.pt", "size": 5, "mtime": "t"}
        )
        daemon.send(
            "/runs/a/files", "file", {"name": "stdout.log", "size": 3000, "mtime": "t"}
        )
        daemon.send("/runs/a/files", "remove", {"name": "run.json"})
        await settle(pilot)
        assert names(browser) == ["ckpt/model.pt", "stdout.log"]
        assert sizes(browser) == ["5 bytes", "3.0 kB"]

    browse(test)


def test_selecting_another_run_lists_its_files_instead() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        browser.post_message(Changed(experiment("a", "b"), daemon=daemon))  # type: ignore[arg-type]
        browser.post_message(Selected("a"))
        await settle(pilot)
        daemon.send(
            "/runs/a/files", "state", [{"name": "a.log", "size": 1, "mtime": "t"}]
        )
        await settle(pilot)
        browser.post_message(Selected("b"))
        browser.post_message(Selected("b"))
        await settle(pilot)
        assert names(browser) == []
        daemon.send(
            "/runs/b/files", "state", [{"name": "b.log", "size": 1, "mtime": "t"}]
        )
        await settle(pilot)
        assert names(browser) == ["b.log"]
        assert daemon.followed == ["/runs/a/files", "/runs/b/files"]
        assert "/runs/a/files" not in daemon.open

    browse(test)


def test_a_run_without_a_folder_yet_is_listed_once_it_has_one() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        browser.post_message(Changed(experiment(), daemon=daemon))  # type: ignore[arg-type]
        browser.post_message(Selected("a"))
        await settle(pilot)
        daemon.reject("/runs/a/files")
        await settle(pilot)
        assert "No files yet" in title(browser, "#files-title")
        browser.post_message(Changed(experiment(), daemon=daemon))  # type: ignore[arg-type]
        await settle(pilot)
        assert daemon.followed == ["/runs/a/files"]
        browser.post_message(Changed(experiment("a"), daemon=daemon))  # type: ignore[arg-type]
        await settle(pilot)
        assert daemon.followed == ["/runs/a/files", "/runs/a/files"]

    browse(test)


async def open_file(
    pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon, name: str
) -> None:
    browser.post_message(Changed(experiment("a"), daemon=daemon))  # type: ignore[arg-type]
    browser.post_message(Selected("a"))
    await settle(pilot)
    daemon.send(
        "/runs/a/files",
        "state",
        [
            {"name": "plot.png", "size": 9, "mtime": "t"},
            {"name": name, "size": 4, "mtime": "t"},
        ],
    )
    await settle(pilot)
    table = browser.query_one("#files", DataTable)
    table.focus()
    table.move_cursor(row=names(browser).index(name))
    await pilot.press("enter")
    await settle(pilot)


def test_selecting_a_file_tails_it_and_follows_new_lines() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        await open_file(pilot, browser, daemon, "stdout.log")
        route = "/runs/a/files/stdout.log"
        assert route in daemon.followed
        daemon.send(
            route, "state", {"name": "stdout.log", "size": 8, "text": "one\ntwo\n"}
        )
        await settle(pilot)
        assert tail(browser) == ["one", "two"]
        assert "stdout.log" in title(browser, "#tail-title")
        daemon.send(route, "append", {"text": "thr"})
        daemon.send(route, "append", {"text": "ee\nfour\n"})
        await settle(pilot)
        assert tail(browser) == ["one", "two", "three", "four"]
        daemon.send(route, "state", {"name": "stdout.log", "size": 4, "text": "new\n"})
        await settle(pilot)
        assert tail(browser) == ["new"]

    browse(test)


def test_a_binary_file_shows_its_type_and_size_not_its_bytes() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        await open_file(pilot, browser, daemon, "plot.png")
        route = "/runs/a/files/plot.png"
        daemon.send(
            route, "state", {"name": "plot.png", "size": 2048, "type": "image/png"}
        )
        await settle(pilot)
        assert tail(browser) == ["Binary file (image/png, 2.0 kB), not shown."]

    browse(test)


def test_a_file_that_is_gone_says_so() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        await open_file(pilot, browser, daemon, "stdout.log")
        daemon.reject("/runs/a/files/stdout.log")
        await settle(pilot)
        assert tail(browser) == ["stdout.log is gone."]

    browse(test)


def test_names_are_quoted_in_routes() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        await open_file(pilot, browser, daemon, "my log#1.txt")
        assert "/runs/a/files/my%20log%231.txt" in daemon.followed

    browse(test)


def test_switching_runs_stops_the_tail() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        await open_file(pilot, browser, daemon, "stdout.log")
        daemon.send(
            "/runs/a/files/stdout.log",
            "state",
            {"name": "stdout.log", "size": 4, "text": "one\n"},
        )
        await settle(pilot)
        browser.post_message(Selected("b"))
        await settle(pilot)
        assert "/runs/a/files/stdout.log" not in daemon.open
        assert tail(browser) == []

    browse(test)


def test_tail_widget_keeps_at_most_max_lines() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        assert browser.query_one("#tail", Log).max_lines == FileBrowser.MAX_LINES

    browse(test)


def test_the_cursor_stays_on_its_file_as_files_arrive_above_it() -> None:
    async def test(
        pilot: Pilot[None], browser: FileBrowser, daemon: FakeDaemon
    ) -> None:
        browser.post_message(Changed(experiment("a"), daemon=daemon))  # type: ignore[arg-type]
        browser.post_message(Selected("a"))
        await settle(pilot)
        files = [{"name": name, "size": 1, "mtime": "t"} for name in ("b.log", "c.log")]
        daemon.send("/runs/a/files", "state", files)
        await settle(pilot)
        table = browser.query_one("#files", DataTable)
        table.move_cursor(row=1)
        daemon.send("/runs/a/files", "file", {"name": "a.log", "size": 1, "mtime": "t"})
        await settle(pilot)
        assert names(browser) == ["a.log", "b.log", "c.log"]
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key == "c.log"

    browse(test)
