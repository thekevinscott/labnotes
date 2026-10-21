import asyncio
import os
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
    await page.get_by_role("textbox", name="Note").get_by_text("The plan").click()
    await expect(page.get_by_role("textbox", name="Note")).to_be_focused()


async def click_into(page: Page, text: str, offset: int) -> None:
    """Click just inside the character at offset in the first rendered text."""
    await expect(page.get_by_role("textbox", name="Note")).to_be_visible()
    x, y = await page.evaluate(
        """([text, offset]) => {
            const editor = document.querySelector(".cm-content");
            const walk = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
            for (let node; (node = walk.nextNode()); ) {
                const at = node.textContent.indexOf(text);
                if (at < 0) continue;
                const range = document.createRange();
                range.setStart(node, at + offset);
                range.setEnd(node, at + offset + 1);
                const box = range.getBoundingClientRect();
                return [box.left + 1, box.top + box.height / 2];
            }
        }""",
        [text, offset],
    )
    await page.mouse.click(x, y)


LINE_TOPS = (
    "() => [...document.querySelectorAll('.cm-line, .cell-below')]"
    ".map((line) => line.getBoundingClientRect().top)"
)

LIVE = (
    "# The plan\n\nSome `inline code` and a [link](https://example.com).\n\n"
    "- First item\n- Second item\n\n> Quoted\n\n## Code\n\n"
    "```python\n1 + 1\n```\n\nAfter.\n"
)


def test_saves_edits_to_the_file(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)
        await page.keyboard.press("End")
        await page.keyboard.type(" revised")

        await on_disk(root / PLAN, "# The plan revised\n")
        await page.keyboard.press("Escape")

        editor = page.get_by_role("textbox", name="Note")
        await expect(editor).not_to_be_focused()
        await expect(editor.locator(".cm-line").first).to_have_text("The plan revised")

    browse(f"{site}{NOTE}", check)


def test_renders_the_note_in_the_editor_with_markup_hidden(root: Path) -> None:
    write(root / PLAN, LIVE)

    async def check(page: Page) -> None:
        editor = page.get_by_role("textbox", name="Note")
        await expect(editor).to_be_visible()
        await expect(editor).not_to_be_focused()
        await expect(page.locator(".prose")).to_have_count(0)
        lines = editor.locator(".cm-line")
        await expect(lines.first).to_have_text("The plan")
        await expect(editor).not_to_contain_text("`")
        await expect(editor).not_to_contain_text("](")
        await expect(editor).not_to_contain_text("> Quoted")

    for site in serve(root):
        browse(f"{site}{NOTE}", check)


def test_shows_markup_only_on_the_line_with_the_cursor(root: Path) -> None:
    write(root / PLAN, LIVE)

    async def check(page: Page) -> None:
        editor = page.get_by_role("textbox", name="Note")
        await click_into(page, "Code", 1)

        await expect(editor.locator(".cm-line").nth(9)).to_have_text("## Code")
        await expect(editor.locator(".cm-line").first).to_have_text("The plan")

    for site in serve(root):
        browse(f"{site}{NOTE}", check)


def test_puts_the_cursor_where_the_click_lands(root: Path) -> None:
    write(root / PLAN, LIVE)

    async def check(page: Page) -> None:
        await click_into(page, "Second item", 3)
        await page.keyboard.type("X")

        await on_disk(root / PLAN, "- SecXond item\n")

    for site in serve(root):
        browse(f"{site}{NOTE}", check)


def test_keeps_the_layout_when_clicked(root: Path) -> None:
    write(root / PLAN, LIVE)

    async def check(page: Page) -> None:
        editor = page.get_by_role("textbox", name="Note")
        await expect(editor.locator(".cm-line").first).to_have_text("The plan")
        for text in ["The plan", "Code", "Second item", "inline code", "Quoted", "+"]:
            before = await page.evaluate(LINE_TOPS)
            await click_into(page, text, 1)
            await expect(editor).to_be_focused()
            await page.wait_for_timeout(200)
            assert await page.evaluate(LINE_TOPS) == before, text

    for site in serve(root):
        browse(f"{site}{NOTE}", check)


def test_leaves_the_file_alone_until_edited(root: Path) -> None:
    write(root / PLAN, LIVE)
    saved = (root / PLAN).read_bytes()

    async def check(page: Page) -> None:
        puts: list[str] = []
        page.on("request", lambda r: puts.append(r.url) if r.method == "PUT" else None)
        editor = page.get_by_role("textbox", name="Note")
        await expect(editor).to_be_visible()
        await click_into(page, "Second item", 2)
        await page.keyboard.press("ArrowDown")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1500)

        assert puts == []

    for site in serve(root):
        browse(f"{site}{NOTE}", check)
    assert (root / PLAN).read_bytes() == saved


def test_edits_markdown_that_looks_like_html(root: Path) -> None:
    write(root / PLAN, "\n# The plan\n\n`</script> & <b>`\n")

    async def check(page: Page) -> None:
        await open_editor(page)
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
        editor = page.get_by_role("textbox", name="Note")
        await expect(editor).to_contain_text("The plan")
        write(root / PLAN, "# Changed elsewhere\n")

        await expect(editor).to_have_text("Changed elsewhere")

    browse(f"{site}{NOTE}", check)


def test_keeps_the_page_when_the_file_is_touched(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await expect(page.get_by_role("textbox", name="Note")).to_be_visible()
        await page.evaluate("window.loaded = true")

        async with page.expect_response(lambda r: r.url.endswith("/notes/plan.md")):
            os.utime(root / PLAN)

        assert await page.evaluate("window.loaded") is True

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


def test_reloads_a_clean_editor_without_a_notice(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)

        write(root / PLAN, "# The plan\n\nTheirs.\n")

        await expect(page.get_by_role("textbox", name="Note")).to_contain_text(
            "Theirs."
        )
        await expect(page.locator(".edit-status")).to_be_hidden()

    browse(f"{site}{NOTE}", check)


def test_tells_of_a_merge_into_unsaved_edits_and_keeps_the_cursor(
    site: str, root: Path
) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)
        await page.keyboard.press("End")
        await page.keyboard.type(" mine")

        write(root / PLAN, "# The plan\n\nTheirs.\n\n```python\n1 + 1\n```\n")

        await expect(
            page.get_by_text(
                "plan.md was modified externally, merging changes automatically"
            )
        ).to_be_visible()
        await expect(page.get_by_role("textbox", name="Note")).to_be_focused()
        await page.keyboard.type(" too")
        await on_disk(
            root / PLAN, "# The plan mine too\n\nTheirs.\n\n```python\n1 + 1\n```\n"
        )

    browse(f"{site}{NOTE}", check)


def test_keeps_both_versions_when_edits_will_not_merge(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await page.route("**/changes", lambda route: route.abort())
        await page.reload()
        await open_editor(page)
        write(root / PLAN, "# Theirs\n\n```python\n1 + 1\n```\n")
        await page.keyboard.press("Control+a")
        await page.keyboard.type("# Mine")

        status = page.locator(".edit-status")
        await expect(status).to_contain_text("could not be merged")
        await on_disk(root / PLAN, "# Mine")
        [copy] = (root / "alpha/files").glob("plan (Conflicted copy *).md")
        assert copy.read_text(encoding="utf-8") == "# Theirs\n\n```python\n1 + 1\n```\n"
        await expect(status).to_contain_text(copy.name)
        await expect(page.get_by_role("textbox", name="Note")).to_have_text("# Mine")
        await expect(page.get_by_role("textbox", name="Note")).to_be_focused()

    browse(f"{site}{NOTE}", check)


def test_saves_during_continuous_typing(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)
        await page.keyboard.press("End")
        typing = asyncio.create_task(page.keyboard.type(" " + "x" * 40, delay=100))

        await on_disk(root / PLAN, "# The plan xxxx")

        assert not typing.done()
        await typing

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

        await page.get_by_role("heading", name="The plan").click()
        await expect(page.get_by_role("textbox", name="Note")).to_have_count(0)
        await page.get_by_role("button", name="Run").click()
        await expect(page.locator(".cell-output")).to_contain_text("2")

    browse(f"{site}{NOTE}", check)


def test_plus_creates_a_note_and_opens_it_for_editing(site: str, root: Path) -> None:
    write(root / "alpha/files/Untitled.md", "# Taken\n")

    async def check(page: Page) -> None:
        await page.evaluate("window.loaded = true")
        await page.get_by_role("button", name="New note").click()

        await expect(page.get_by_role("textbox", name="Note")).to_be_focused()
        await expect(page.get_by_role("link", name="Untitled 2.md")).to_have_attribute(
            "aria-current", "page"
        )
        await expect(page.get_by_role("link", name="plan.md")).not_to_have_attribute(
            "aria-current", "page"
        )
        await expect(page.get_by_role("link", name="Notebooks 4")).to_be_visible()
        assert page.url.endswith("?tab=notebooks&note=Untitled%202.md")
        assert await page.evaluate("window.loaded") is True
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
        await expect(page.get_by_role("link", name="Untitled.md")).to_be_visible()
        assert (root / "alpha/files/Untitled.md").read_text(
            encoding="utf-8"
        ) == "# Untitled\n"
        await page.keyboard.press("End")
        await page.keyboard.type(" first")
        await on_disk(root / "alpha/files/Untitled.md", "# Untitled first\n")
        await page.keyboard.press("Escape")
        await expect(page.get_by_role("textbox", name="Note")).to_have_text(
            "Untitled first"
        )

    for site in serve(root):
        browse(f"{site}/experiments/alpha?tab=notebooks", check)


def test_plus_keeps_an_edit_in_progress(site: str, root: Path) -> None:
    async def check(page: Page) -> None:
        await open_editor(page)
        await page.keyboard.press("End")
        await page.keyboard.type(" unsaved")
        await page.get_by_role("button", name="New note").click()

        await expect(page.get_by_role("textbox", name="Note")).to_be_focused()
        await expect(page.get_by_role("link", name="Untitled.md")).to_have_attribute(
            "aria-current", "page"
        )
        await on_disk(root / PLAN, "# The plan unsaved\n")
        await page.keyboard.type("new ")
        await on_disk(root / "alpha/files/Untitled.md", "new # Untitled\n")

    browse(f"{site}{NOTE}", check)
