import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.async_api import Page, expect
from conftest import browse, project, serve, write

PLAN = "alpha/files/plan.md"
NOTE = "/experiments/alpha?tab=notebooks&note=plan.md"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return project(tmp_path)


@pytest.fixture
def site(root: Path) -> Iterator[str]:
    yield from serve(root)


async def on_disk(path: Path, text: str) -> None:
    for _ in range(50):
        if text in path.read_text(encoding="utf-8"):
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"{text!r} never reached {path}")


async def open_editor(page: Page) -> None:
    await page.get_by_role("heading", name="The plan").click()
    await expect(page.get_by_role("textbox", name="Note")).to_be_focused()


def test_saves_edits_to_the_file_and_shows_them(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)
        await page.keyboard.press("End")
        await page.keyboard.type(" revised")

        await on_disk(root / PLAN, "# The plan revised\n")
        await page.keyboard.press("Escape")

        await expect(
            page.get_by_role("heading", name="The plan revised")
        ).to_be_visible()
        await expect(page.get_by_role("textbox", name="Note")).to_have_count(0)

    browse(f"{site}{NOTE}", check)


def test_edits_markdown_that_looks_like_html(root: Path) -> None:
    write(root / PLAN, "\n# The plan\n\n`</script> & <b>`\n")

    async def check(page: Page) -> None:
        await open_editor(page)
        await page.keyboard.press("ArrowDown")
        await page.keyboard.press("End")
        await page.keyboard.type("!")

        await on_disk(root / PLAN, "\n# The plan!\n\n`</script> & <b>`\n")

    for site in serve(root):
        browse(f"{site}{NOTE}", check)


def test_runs_a_block_as_edited(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)
        await page.get_by_role("textbox", name="Note").get_by_text("1 + 1").click()
        await page.keyboard.press("End")
        await page.keyboard.type("0")
        await on_disk(root / PLAN, "1 + 10\n")
        await page.mouse.click(5, 5)

        await page.get_by_role("button", name="Run").click()

        await expect(page.locator(".cell-output")).to_contain_text("11")

    browse(f"{site}{NOTE}", check)


def test_keeps_edits_when_the_file_changed_on_disk(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        write(root / PLAN, "# Changed elsewhere\n")
        await open_editor(page)
        await page.keyboard.type("mine ")

        await expect(page.get_by_text("This note changed on disk")).to_be_visible()
        await page.keyboard.press("Escape")
        await expect(page.get_by_role("textbox", name="Note")).to_be_visible()
        assert (root / PLAN).read_text(encoding="utf-8") == "# Changed elsewhere\n"

    browse(f"{site}{NOTE}", check)


def test_reads_and_runs_offline_without_the_editor(site: str) -> None:
    async def check(page: Page) -> None:
        await page.route("https://esm.sh/**", lambda route: route.abort())
        await page.reload()

        await expect(page.get_by_text("Editing needs the network")).to_be_visible()
        await page.get_by_role("heading", name="The plan").click()
        await expect(page.get_by_role("textbox", name="Note")).to_have_count(0)
        await page.get_by_role("button", name="Run").click()
        await expect(page.locator(".cell-output")).to_contain_text("2")

    browse(f"{site}{NOTE}", check)
