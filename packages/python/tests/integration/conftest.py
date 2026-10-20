import asyncio
import json
import socket
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

import pytest
from playwright.async_api import Page, async_playwright

CONFIG = (
    'name = "Alpha study"\ncommand = "go"\nrepeats = 2\nmode = "fill"\n'
    '[params]\nsource-language = ["en", "fr"]\n'
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(project: Path, name: str, params: dict[str, object], **fields: object) -> None:
    record = {"params": params, "created": f"2026-10-17T00:00:0{name[-1]}Z", **fields}
    write(project / f"alpha/runs/{name}/run.json", json.dumps(record))


def project(root: Path) -> Path:
    write(root / "beta/files/notes.md", "beta notes")
    write(root / ".labnotes.toml", "")
    write(root / "alpha/experiment.toml", CONFIG)
    write(root / "alpha/files/plan.md", "# The plan\n\n```python\n1 + 1\n```\n")
    write(root / "alpha/files/results.md", "# Results\n\nAll good.\n")
    run(root, "run1", {"source-language": "en"}, exit_code=0)
    run(root, "run2", {"source-language": "fr"}, exit_code=1, stdout="boom")
    return root


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve(root: Path) -> Iterator[str]:
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
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait()


def browse(
    url: str, check: Callable[[Page], Awaitable[None]], width: int = 1280
) -> None:
    async def drive() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": width, "height": 800})
            await page.goto(url)
            await check(page)
            await browser.close()

    asyncio.run(drive())


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    yield from serve(project(tmp_path))
