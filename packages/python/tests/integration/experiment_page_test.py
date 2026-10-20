import asyncio
import json
import socket
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

import pytest
from playwright.async_api import Page, async_playwright, expect

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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve(project: Path) -> Iterator[str]:
    port = free_port()
    labnotes = Path(sys.executable).parent / "labnotes"
    process = subprocess.Popen(
        [labnotes, "-c", project / ".labnotes.toml", "server", "-p", str(port)],
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


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    write(tmp_path / "beta/files/notes.md", "beta notes")
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", CONFIG)
    write(tmp_path / "alpha/files/plan.md", "# The plan\n\n```python\n1 + 1\n```\n")
    write(tmp_path / "alpha/files/results.md", "# Results\n\nAll good.\n")
    run(tmp_path, "run1", {"source-language": "en"}, exit_code=0)
    run(tmp_path, "run2", {"source-language": "fr"}, exit_code=1, stdout="boom")
    yield from serve(tmp_path)


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


def test_shows_the_experiment_toml_on_one_line(site: str) -> None:
    async def check(page: Page) -> None:
        await expect(page.get_by_role("heading", name="Alpha study")).to_be_visible()
        summary = page.locator(".config-summary")
        await expect(summary).to_contain_text("fill")
        await expect(summary).to_contain_text("command go")
        await expect(summary).to_contain_text("repeats 2")
        await expect(summary).to_contain_text("source-language en fr")
        await expect(page.get_by_role("button", name="experiment.toml")).to_be_hidden()

    browse(f"{site}/experiments/alpha", check)


def test_opens_a_long_experiment_toml_in_a_modal(site: str) -> None:
    async def check(page: Page) -> None:
        await page.get_by_role("button", name="experiment.toml").click()

        dialog = page.get_by_role("dialog")
        await expect(dialog).to_contain_text('source-language = ["en", "fr"]')
        await dialog.get_by_role("button", name="Close").click()
        await expect(dialog).to_be_hidden()

    browse(f"{site}/experiments/alpha", check, width=420)


def test_lists_runs_in_a_table_that_expands_a_run(site: str) -> None:
    async def check(page: Page) -> None:
        await expect(page.get_by_role("link", name="Runs 2")).to_have_attribute(
            "aria-current", "page"
        )
        table = page.get_by_role("table")
        header = table.get_by_role("columnheader", name="source-language")
        await expect(header).to_be_visible()
        await expect(page.get_by_text("boom")).to_be_hidden()

        await table.get_by_role("row").filter(has_text="run2").first.click()

        await expect(page.get_by_text("boom")).to_be_visible()

    browse(f"{site}/experiments/alpha", check)


def test_filters_runs_by_a_param(site: str) -> None:
    async def check(page: Page) -> None:
        await page.get_by_label("Filter source-language").fill("fr")
        await page.get_by_label("Filter source-language").press("Enter")

        await expect(page.get_by_role("cell", name="run2", exact=True)).to_be_visible()
        await expect(page.get_by_role("cell", name="run1", exact=True)).to_have_count(0)

    browse(f"{site}/experiments/alpha", check)


def test_switches_between_notebooks(site: str) -> None:
    async def check(page: Page) -> None:
        await page.get_by_role("link", name="Notebooks 2").click()
        await expect(page.get_by_role("heading", name="The plan")).to_be_visible()
        await expect(page.get_by_role("table")).to_have_count(0)

        await page.get_by_role("link", name="results.md").click()

        await expect(page.get_by_role("heading", name="Results")).to_be_visible()
        await expect(page.get_by_role("heading", name="The plan")).to_have_count(0)
        await expect(page.get_by_role("link", name="results.md")).to_have_attribute(
            "aria-current", "page"
        )

    browse(f"{site}/experiments/alpha", check)


def test_shows_an_experiment_without_a_config(site: str) -> None:
    async def check(page: Page) -> None:
        await expect(page.get_by_text("No runs recorded yet.")).to_be_visible()
        await expect(page.locator(".config-summary")).to_have_count(0)

        await page.get_by_role("link", name="Notebooks 1").click()

        await expect(page.get_by_text("beta notes")).to_be_visible()

    browse(f"{site}/experiments/beta", check)


def test_shows_a_broken_counts_rule(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/experiment.toml",
        'command = "go"\ncounts = "nope ="\n[params]\nm = ["a"]\n',
    )
    run(tmp_path, "run1", {"m": "a"}, exit_code=0)

    async def check(page: Page) -> None:
        await expect(page.locator(".config-summary")).to_contain_text(
            "nope = doesn't work: SQLite error"
        )

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)
