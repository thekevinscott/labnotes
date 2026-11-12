import asyncio
import json
import os
import socket
import subprocess
import time
from pathlib import Path

import psutil
from playwright.async_api import async_playwright, expect


def inotify_watches(pid: int) -> int:
    watches = 0
    for process in [psutil.Process(pid), *psutil.Process(pid).children(True)]:
        for fd in os.listdir(f"/proc/{process.pid}/fd"):
            try:
                if os.readlink(f"/proc/{process.pid}/fd/{fd}") != "anon_inode:inotify":
                    continue
                info = Path(f"/proc/{process.pid}/fdinfo/{fd}").read_text()
            except FileNotFoundError:
                continue
            watches += sum(line.startswith("inotify wd:") for line in info.splitlines())
    return watches


async def settled(pid: int, expected: int) -> None:
    for _ in range(50):
        if inotify_watches(pid) == expected:
            return
        await asyncio.sleep(0.1)
    assert inotify_watches(pid) == expected


def test_installed_server_watches_only_what_a_page_follows(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "alpha/files").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "alpha/experiment.toml").write_text('continues = false\ncommand = "true"\n')
    for name in ("a", "b", "c", "d", "e"):
        (root / f"data/{name}/deep/more").mkdir(parents=True)
    folder = root / "alpha/runs/run1"
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(
        json.dumps({"params": {}, "created": "2026-11-06T00:00:01Z"})
    )
    (folder / "stdout.log").write_text("out one\n")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml")]
        + ["server", "-p", str(port)],
        env={**os.environ, **uvx},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    site = f"http://127.0.0.1:{port}"

    async def check() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"{site}/experiments/alpha")
            await expect(
                page.get_by_role("row").filter(has_text="run1")
            ).to_be_visible()
            await asyncio.sleep(1)
            assert inotify_watches(server.pid) == 0

            await page.goto(f"{site}/experiments/alpha/runs/run1")
            stdout = page.locator("#run-stdout")
            await expect(stdout).to_have_text("out one")
            await settled(server.pid, 1)
            with (folder / "stdout.log").open("a") as log:
                log.write("out two\n")
            await expect(stdout).to_have_text("out one\nout two", use_inner_text=True)

            await page.goto(f"{site}/")
            await settled(server.pid, 0)
            await browser.close()

    try:
        for _ in range(300):
            try:
                socket.create_connection(("127.0.0.1", port)).close()
                break
            except OSError:
                assert server.poll() is None, "server exited"
                time.sleep(0.1)
        asyncio.run(check())
    finally:
        server.terminate()
        server.wait(timeout=10)
