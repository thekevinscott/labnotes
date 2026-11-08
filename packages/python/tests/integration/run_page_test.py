import json
from pathlib import Path

from playwright.async_api import Page, expect
from conftest import browse, run, serve, write


def test_follows_a_running_runs_output_until_it_ends(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
    run(tmp_path, "run1", {"model": "opus"})
    folder = tmp_path / "alpha/runs/run1"
    write(folder / "stdout.log", "starting\n")
    write(folder / "stderr.log", "")

    async def check(page: Page) -> None:
        row = page.get_by_role("row").filter(has_text="run1")
        await row.get_by_role("cell").last.click()
        await expect(page).to_have_url(f"{site}/experiments/alpha/runs/run1")
        await expect(page.locator(".run-state")).to_have_text("running")
        stdout, stderr = page.locator("#run-stdout"), page.locator("#run-stderr")
        await expect(stdout).to_have_text("starting")
        await expect(page.get_by_role("tab")).to_have_text(["stdout (1)", "stderr (0)"])

        with (folder / "stdout.log").open("a") as log:
            log.write("step 1\nstep")
        with (folder / "stderr.log").open("a") as log:
            log.write("warning\n")
        await expect(stdout).to_have_text("starting\nstep 1\nstep", use_inner_text=True)
        await expect(page.get_by_role("tab")).to_have_text(["stdout (2)", "stderr (1)"])
        await expect(stderr).to_be_hidden()
        await page.get_by_role("tab", name="stderr").click()
        await expect(stderr).to_have_text("warning")
        await expect(stdout).to_be_hidden()
        await expect(page.get_by_role("tab", name="stderr")).to_have_attribute(
            "aria-selected", "true"
        )

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
        await expect(page.locator(".run-log")).to_have_attribute("data-ended", "")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_shows_log_blocks_as_lines_that_open_on_click(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
    run(tmp_path, "run1", {})
    folder = tmp_path / "alpha/runs/run1"
    write(folder / "stdout.log", "printed\n")

    def logged(*records: object) -> None:
        with (folder / "log.jsonl").open("a") as log:
            for record in records:
                log.write(json.dumps(record) + "\n")

    async def check(page: Page) -> None:
        blocks = page.locator(".run-blocks")
        await expect(page.locator("#run-stdout")).to_have_text("printed")
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


def test_keeps_showing_log_blocks_past_invalid_utf8(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
    run(tmp_path, "run1", {})
    folder = tmp_path / "alpha/runs/run1"
    write(folder / "stdout.log", "printed\n")

    async def check(page: Page) -> None:
        (folder / "log.jsonl").write_bytes(
            b'{"content":"ok"}\n{"content":"bad \xff"}\n{"content":"after"}\n'
        )
        await expect(page.locator(".run-blocks").get_by_role("button")).to_have_text(
            ["ok", "bad \ufffd", "after"]
        )

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha/runs/run1", check)


def test_opens_a_nested_runs_page(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
    run(tmp_path, "g1/run1", {}, exit_code=1, ended="2026-10-17T00:00:09Z")
    run(tmp_path, "g1/run2", {}, exit_code=0, ended="2026-10-17T00:00:09Z")
    write(tmp_path / "alpha/runs/g1/run1/stderr.log", "boom\n")

    async def check(page: Page) -> None:
        await page.get_by_role("button", name="g1").click()
        await page.get_by_role("link", name="run1").click()
        await expect(page.get_by_role("heading", name="g1/run1")).to_be_visible()
        await expect(page.locator(".run-state")).to_have_text("exit 1")
        await expect(page.get_by_role("tab")).to_have_text(["stdout (0)", "stderr (1)"])
        await page.get_by_role("tab", name="stderr").click()
        await expect(page.locator("#run-stderr")).to_have_text("boom")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_renders_ansi_color_and_escapes_html(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
    run(tmp_path, "run1", {}, exit_code=0, ended="2026-10-17T00:00:09Z")
    folder = tmp_path / "alpha/runs/run1"
    write(folder / "stdout.log", "\x1b[31mred\x1b[0m <b>plain</b>\n")
    write(folder / "stderr.log", "\x1b[1mbo\x1b[2Kld\x1b[0m\n")

    async def check(page: Page) -> None:
        output = page.locator(".run-log")
        await expect(page.locator("#run-stdout")).to_have_text("red <b>plain</b>")
        red = output.locator("#run-stdout span", has_text="red")
        await expect(red).to_have_css("color", "rgb(187, 0, 0)")
        await expect(output.locator("b")).to_have_count(0)
        await page.get_by_role("tab", name="stderr").click()
        await expect(page.locator("#run-stderr")).to_have_text("bold")
        bold = page.locator("#run-stderr .window span")
        await expect(bold).to_have_text(["bo", "ld"])
        await expect(bold.last).to_have_css("font-weight", "700")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha/runs/run1", check)


def test_shows_why_a_run_failed(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
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


def test_loads_only_the_visible_window_of_a_large_log(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
    run(tmp_path, "run1", {})
    folder = tmp_path / "alpha/runs/run1"
    (folder / "stdout.log").write_bytes(
        b"".join(b"line %d\n" % number for number in range(300_000))
    )

    async def check(page: Page) -> None:
        stdout = page.locator("#run-stdout")
        await expect(page.get_by_role("tab")).to_have_text(
            ["stdout (300000)", "stderr (0)"]
        )
        window = stdout.locator(".window")
        await expect(window).to_contain_text("line 299999")
        assert await window.evaluate("node => node.children.length") < 100
        await stdout.evaluate("pane => { pane.scrollTop = pane.scrollHeight / 2 }")
        await expect(window).to_contain_text("line 150000")
        await expect(window).not_to_contain_text("line 299999")
        with (folder / "stdout.log").open("ab") as log:
            log.write(b"line 300000\n")
        await expect(page.get_by_role("tab")).to_have_text(
            ["stdout (300001)", "stderr (0)"]
        )
        await expect(window).to_contain_text("line 150000")
        await stdout.evaluate("pane => { pane.scrollTop = pane.scrollHeight }")
        await expect(window).to_contain_text("line 300000")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha/runs/run1", check)


def test_wraps_long_lines_and_sticks_to_the_bottom(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'continues = false\ncommand = "true"\n')
    run(tmp_path, "run1", {})
    path = tmp_path / "alpha/runs/run1/stdout.log"
    write(
        path, "".join(f"line {number}\n" for number in range(200)) + "x" * 3000 + "\n"
    )

    def append(text: str) -> None:
        with path.open("a") as log:
            log.write(text)

    async def check(page: Page) -> None:
        stdout = page.locator("#run-stdout")
        window = stdout.locator(".window")
        await expect(window.locator("div").last).to_have_text("x" * 3000)
        assert await stdout.evaluate("pane => pane.scrollWidth <= pane.clientWidth")
        long_row = await window.locator("div").last.evaluate("row => row.offsetHeight")
        assert long_row > 40
        append("line 201\n")
        await expect(window.locator("div").last).to_have_text("line 201")
        await stdout.evaluate("pane => { pane.scrollTop = 0 }")
        await expect(window.locator("div").first).to_have_text("line 0")
        append("line 202\n")
        await expect(page.get_by_role("tab").first).to_have_text("stdout (203)")
        await expect(window.locator("div").first).to_have_text("line 0")
        await stdout.evaluate("pane => { pane.scrollTop = pane.scrollHeight }")
        await expect(window.locator("div").last).to_have_text("line 202")
        append("line 203\n")
        await expect(window.locator("div").last).to_have_text("line 203")

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha/runs/run1", check)
