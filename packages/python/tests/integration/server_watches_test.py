import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.async_api import Page, expect
from conftest import browse, free_port, project, run, write

NOTE = "/experiments/alpha?tab=notebooks&note=plan.md"


def inotify_watches(pid: int) -> int:
    watches = 0
    for fd in os.listdir(f"/proc/{pid}/fd"):
        try:
            if os.readlink(f"/proc/{pid}/fd/{fd}") != "anon_inode:inotify":
                continue
            info = Path(f"/proc/{pid}/fdinfo/{fd}").read_text()
        except FileNotFoundError:
            continue
        watches += sum(line.startswith("inotify wd:") for line in info.splitlines())
    return watches


def folders(path: Path) -> int:
    return 1 + sum(1 for found in path.rglob("*") if found.is_dir())


async def settled(pid: int, expected: int) -> None:
    for _ in range(50):
        if inotify_watches(pid) == expected:
            return
        await asyncio.sleep(0.1)
    assert inotify_watches(pid) == expected


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = project(tmp_path)
    run(root, "run3", {"source-language": "en"})
    write(root / "alpha/runs/run3/stdout.log", "starting\n")
    run(root, "run5", {}, ended="2026-10-17T00:00:09Z", exit_code=0)
    for name in ("a", "b", "c", "d", "e"):
        write(root / f"data/{name}/deep/more/file.txt", name)
    return root


@pytest.fixture
def server(root: Path) -> Iterator[tuple[str, int]]:
    port = free_port()
    labnotes = Path(sys.executable).parent / "labnotes"
    process = subprocess.Popen(
        [labnotes, "-c", root / ".labnotes.toml", "server", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port)).close()
                break
            except OSError:
                time.sleep(0.1)
        yield f"http://127.0.0.1:{port}", process.pid
    finally:
        process.terminate()
        process.wait()


def test_serving_pages_adds_no_inotify_watches(server: tuple[str, int]) -> None:
    site, pid = server

    async def check(page: Page) -> None:
        await expect(page.get_by_role("link", name="Alpha study")).to_be_visible()
        await page.goto(f"{site}/experiments/alpha")
        await expect(page.get_by_role("row").filter(has_text="run5")).to_be_visible()
        await page.goto(f"{site}/experiments/alpha/runs/run5")
        await expect(page.locator(".run-state")).to_have_text("exit 0")
        await asyncio.sleep(1)

        assert inotify_watches(pid) == 0

    browse(f"{site}/", check)


def test_a_running_runs_page_watches_only_its_folder_and_updates_live(
    server: tuple[str, int], root: Path
) -> None:
    site, pid = server
    folder = root / "alpha/runs/run3"

    async def check(page: Page) -> None:
        stdout = page.locator("#run-stdout")
        await expect(stdout).to_have_text("starting")

        await settled(pid, folders(folder))

        with (folder / "stdout.log").open("a") as log:
            log.write("step 1\n")
        await expect(stdout).to_have_text("starting\nstep 1", use_inner_text=True)

        await page.goto(f"{site}/")
        await settled(pid, 0)

    browse(f"{site}/experiments/alpha/runs/run3", check)


def test_an_open_note_watches_only_the_notes_folder_and_updates_live(
    server: tuple[str, int], root: Path
) -> None:
    site, pid = server

    async def check(page: Page) -> None:
        note = page.get_by_role("textbox", name="Note")
        await expect(note.get_by_text("The plan")).to_be_visible()

        await settled(pid, folders(root / "alpha/files"))

        write(root / "alpha/files/plan.md", "# The new plan\n")
        await expect(note.get_by_text("The new plan")).to_be_visible()

        await page.goto(f"{site}/")
        await settled(pid, 0)

    browse(f"{site}{NOTE}", check)
