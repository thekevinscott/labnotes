from pathlib import Path

from playwright.async_api import Page, expect
from conftest import browse, run, serve, write


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


def test_runs_a_block_and_keeps_its_output(site: str) -> None:
    async def check(page: Page) -> None:
        await page.get_by_role("link", name="Notebooks 2").click()
        await page.get_by_role("button", name="Run").click()
        await expect(page.locator(".cell-output")).to_have_text("2", timeout=30_000)

        await page.reload()

        await expect(page.locator(".cell-output")).to_have_text("2")

    browse(f"{site}/experiments/alpha", check)


def test_restart_clears_the_notebook_state(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/files/plan.md",
        "```python\na = 1\n```\n\n```python\na\n```\n",
    )

    async def check(page: Page) -> None:
        await page.get_by_role("link", name="Notebooks 1").click()
        runs = page.get_by_role("button", name="Run")
        outputs = page.locator(".cell-output")
        await runs.first.click()
        await runs.last.click()
        await expect(outputs.last).to_have_text("1", timeout=30_000)

        await page.get_by_role("button", name="Restart").click()
        await expect(page.get_by_role("button", name="Restarted")).to_be_visible(
            timeout=30_000
        )
        await runs.last.click()

        await expect(outputs.last).to_contain_text("NameError", timeout=30_000)

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)
