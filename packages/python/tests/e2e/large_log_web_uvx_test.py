import asyncio
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright, expect


def test_installed_server_pages_through_a_large_log(
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
    (folder / "stdout.log").write_bytes(
        b"".join(b"line %d\n" % number for number in range(500_000))
    )
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
            await expect(page.get_by_role("tab")).to_have_text(
                ["stdout (500000)", "stderr (0)"]
            )
            stdout = page.locator("#run-stdout")
            window = stdout.locator(".window")
            await expect(window).to_contain_text("line 499999")
            held = await window.evaluate("node => node.textContent.split('\\n').length")
            assert held < 300
            await stdout.evaluate("pane => { pane.scrollTop = 0 }")
            await expect(window).to_contain_text("line 0\nline 1\n")
            await expect(window).not_to_contain_text("line 499999")
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
