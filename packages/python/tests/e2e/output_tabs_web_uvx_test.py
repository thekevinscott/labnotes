import asyncio
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright, expect


def test_installed_server_shows_stdout_and_stderr_in_separate_tabs(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha/experiment.toml").write_text(
        'continues = false\ncommand = "true"\n'
    )
    folder = tmp_path / "alpha/runs/run1"
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(
        json.dumps(
            {
                "params": {},
                "created": "2026-11-06T00:00:01Z",
                "ended": "2026-11-06T00:00:09Z",
                "exit_code": 0,
            }
        )
    )
    (folder / "stdout.log").write_text("out one\nout two\nout three\n")
    (folder / "stderr.log").write_text("err one\nerr two\n")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        ["uvx", "labnotes", "-c", str(tmp_path / ".labnotes.toml")]
        + ["server", "-p", str(port)],
        env={**os.environ, **uvx},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    async def check() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{port}/experiments/alpha/runs/run1")
            tabs = page.get_by_role("tab")
            await expect(tabs).to_have_text(["stdout (3)", "stderr (2)"])
            await expect(page.get_by_text("out three")).to_be_visible()
            await expect(page.get_by_text("err one")).to_be_hidden()
            await page.get_by_role("tab", name="stderr").click()
            await expect(page.get_by_text("err two")).to_be_visible()
            await expect(page.get_by_text("out one")).to_be_hidden()
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
