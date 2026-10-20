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


def test_shows_an_outside_edit_in_the_rendered_note(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await expect(page.get_by_role("heading", name="The plan")).to_be_visible()
        write(root / PLAN, "# Changed elsewhere\n")

        await expect(
            page.get_by_role("heading", name="Changed elsewhere")
        ).to_be_visible()

    browse(f"{site}{NOTE}", check)


def test_merges_an_outside_edit_into_the_open_editor(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)
        await page.keyboard.press("End")
        await page.keyboard.type(" mine")
        await on_disk(root / PLAN, "# The plan mine\n")

        write(root / PLAN, "# The plan mine\n\nTheirs.\n\n```python\n1 + 1\n```\n")
        editor = page.get_by_role("textbox", name="Note")
        await expect(editor).to_contain_text("Theirs.")
        await page.keyboard.type(" too")

        await on_disk(
            root / PLAN, "# The plan mine too\n\nTheirs.\n\n```python\n1 + 1\n```\n"
        )

    browse(f"{site}{NOTE}", check)


def test_merges_when_a_save_finds_the_file_changed(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await page.route("**/changes", lambda route: route.abort())
        await page.reload()
        await open_editor(page)
        write(root / PLAN, "# The plan\n\nTheirs.\n\n```python\n1 + 1\n```\n")
        await page.keyboard.press("End")
        await page.keyboard.type(" mine")

        await on_disk(
            root / PLAN, "# The plan mine\n\nTheirs.\n\n```python\n1 + 1\n```\n"
        )
        await expect(page.get_by_role("textbox", name="Note")).to_contain_text(
            "Theirs."
        )

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


def test_plus_creates_a_note_and_opens_it_for_editing(site: str, root: Path) -> None:
    write(root / "alpha/files/Untitled.md", "# Taken\n")

    async def check(page: Page) -> None:
        await page.get_by_role("button", name="New note").click()

        await expect(page.get_by_role("textbox", name="Note")).to_be_focused()
        await expect(page.get_by_role("link", name="Untitled 2.md")).to_have_attribute(
            "aria-current", "page"
        )
        await page.keyboard.press("End")
        await page.keyboard.type(" notes")
        await on_disk(root / "alpha/files/Untitled 2.md", "# Untitled notes\n")
        assert (root / "alpha/files/Untitled.md").read_text(
            encoding="utf-8"
        ) == "# Taken\n"

    browse(f"{site}{NOTE}", check)


def test_plus_starts_the_first_note(tmp_path: Path) -> None:
    root = project(tmp_path)
    for note in (root / "alpha/files").iterdir():
        note.unlink()

    async def check(page: Page) -> None:
        await expect(page.get_by_text("No notebooks yet.")).to_be_visible()
        await page.get_by_role("button", name="New note").click()

        await expect(page.get_by_role("textbox", name="Note")).to_be_focused()
        assert (root / "alpha/files/Untitled.md").read_text(
            encoding="utf-8"
        ) == "# Untitled\n"

    for site in serve(root):
        browse(f"{site}/experiments/alpha?tab=notebooks", check)
