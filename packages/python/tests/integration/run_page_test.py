import json
from pathlib import Path

from playwright.async_api import Page, expect
from conftest import browse, run, serve, write


def test_follows_a_running_runs_output_until_it_ends(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'command = "true"\n')
    run(tmp_path, "run1", {"model": "opus"})
    folder = tmp_path / "alpha/runs/run1"
    write(folder / "stdout.log", "starting\n")
    write(folder / "stderr.log", "")

    async def check(page: Page) -> None:
        row = page.get_by_role("row").filter(has_text="run1")
        await row.get_by_role("cell").last.click()
        await expect(page).to_have_url(f"{site}/experiments/alpha/runs/run1")
        await expect(page.locator(".run-state")).to_have_text("running")
        output = page.locator(".run-output")
        await expect(output).to_have_text("starting\n")

        with (folder / "stdout.log").open("a") as log:
            log.write("step 1\n")
        with (folder / "stderr.log").open("a") as log:
            log.write("warning\n")
        await expect(output).to_have_text("starting\nstep 1\nwarning\n")
        await expect(output.locator(".stderr")).to_have_text("warning\n")

        write(
            folder / "run.json",
            json.dumps(
                {
                    "params": {"model": "opus"},
                    "created": "2026-10-17T00:00:01Z",
                    "ended": "2026-10-17T00:00:09Z",
                    "exit_code": 0,
                }
            ),
        )
        await expect(page.locator(".run-state")).to_have_text("exit 0")
        await expect(output).to_have_attribute("data-ended", "")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_shows_log_blocks_as_lines_that_open_on_click(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'command = "true"\n')
    run(tmp_path, "run1", {})
    folder = tmp_path / "alpha/runs/run1"
    write(folder / "stdout.log", "printed\n")

    def logged(*records: object) -> None:
        with (folder / "log.jsonl").open("a") as log:
            for record in records:
                log.write(json.dumps(record) + "\n")

    async def check(page: Page) -> None:
        blocks = page.locator(".run-blocks")
        await expect(page.locator(".run-output")).to_have_text("printed\n")
        await expect(blocks).to_be_hidden()

        logged(
            {"content": "first line\nsecond line", "timestamp": "t"},
            {"id": "t1", "phase": "start", "type": "thinking"},
            {"id": "t1", "phase": "delta", "content": "think"},
        )
        lines = blocks.get_by_role("button")
        await expect(lines).to_have_text(["first line\nsecond line", "think"])
        first = lines.first
        await expect(first).to_have_css("white-space", "nowrap")
        await expect(first).to_have_css("text-overflow", "ellipsis")
        box = await first.bounding_box()

        await first.click()
        await expect(first).to_have_attribute("aria-expanded", "true")
        await expect(first).to_have_css("white-space", "pre-wrap")
        opened = await first.bounding_box()
        assert box is not None
        assert opened is not None
        assert opened["height"] > box["height"]
        await first.click()
        await expect(first).to_have_attribute("aria-expanded", "false")

        logged(
            {"id": "t1", "phase": "delta", "content": "ing"},
            {"id": "t1", "phase": "stop"},
        )
        await expect(lines).to_have_text(["first line\nsecond line", "thinking"])

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha/runs/run1", check)


def test_opens_a_nested_runs_page(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'command = "true"\nmode = "adhoc"\n')
    run(tmp_path, "g1/run1", {}, exit_code=1, ended="2026-10-17T00:00:09Z")
    run(tmp_path, "g1/run2", {}, exit_code=0, ended="2026-10-17T00:00:09Z")
    write(tmp_path / "alpha/runs/g1/run1/stderr.log", "boom\n")

    async def check(page: Page) -> None:
        await page.get_by_role("button", name="g1").click()
        await page.get_by_role("link", name="run1").click()
        await expect(page.get_by_role("heading", name="g1/run1")).to_be_visible()
        await expect(page.locator(".run-state")).to_have_text("exit 1")
        await expect(page.locator(".run-output .stderr")).to_have_text("boom\n")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_renders_ansi_color_and_escapes_html(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'command = "true"\n')
    run(tmp_path, "run1", {}, exit_code=0, ended="2026-10-17T00:00:09Z")
    folder = tmp_path / "alpha/runs/run1"
    write(folder / "stdout.log", "\x1b[31mred\x1b[0m <b>plain</b>\n")
    write(folder / "stderr.log", "\x1b[1mbo\x1b[2Kld\x1b[0m\n")

    async def check(page: Page) -> None:
        output = page.locator(".run-output")
        await expect(output).to_have_text("red <b>plain</b>\nbold\n")
        red = output.locator(".stdout span", has_text="red")
        await expect(red).to_have_css("color", "rgb(187, 0, 0)")
        await expect(output.locator("b")).to_have_count(0)
        bold = output.locator(".stderr span")
        await expect(bold).to_have_text(["bo", "ld"])
        await expect(bold.last).to_have_css("font-weight", "700")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha/runs/run1", check)


def test_shows_why_a_run_failed(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'command = "true"\n')
    run(
        tmp_path,
        "run1",
        {},
        exit_code=-15,
        error="timed out after 30s",
        ended="2026-10-17T00:00:09Z",
    )

    async def check(page: Page) -> None:
        await page.get_by_role("link", name="run1").click()
        await expect(page.locator(".run-state")).to_have_text("timed out after 30s")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)
