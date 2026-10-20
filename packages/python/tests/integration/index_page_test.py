from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.async_api import Page, expect
from served import browse, project, run, serve, write


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    yield from serve(project(tmp_path))


def test_lists_experiments_with_their_progress(site: str) -> None:
    async def check(page: Page) -> None:
        await expect(
            page.get_by_text("2 experiments, 2 runs recorded.")
        ).to_be_visible()
        alpha = page.get_by_role("row").filter(has_text="Alpha study")
        await expect(alpha).to_contain_text("1/4")
        await expect(alpha).to_contain_text("25%")
        await expect(page.get_by_role("link", name="beta")).to_be_visible()

    browse(site, check)


def test_opens_an_experiment_from_anywhere_on_its_row(site: str) -> None:
    async def check(page: Page) -> None:
        await (
            page.get_by_role("row")
            .filter(has_text="Alpha study")
            .get_by_text("25%")
            .click()
        )

        await expect(page.get_by_role("heading", name="Alpha study")).to_be_visible()

    browse(site, check)


def test_remembers_the_cards_view(site: str) -> None:
    async def check(page: Page) -> None:
        await page.get_by_role("button", name="Cards").click()
        await page.reload()

        await expect(page.get_by_role("button", name="Cards")).to_have_attribute(
            "aria-pressed", "true"
        )
        await expect(page.locator(".ledger")).to_have_attribute("data-view", "cards")

    browse(site, check)


def test_shows_a_broken_counts_rule(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/experiment.toml",
        'command = "go"\ncounts = "nope ="\n[params]\nm = ["a"]\n',
    )
    run(tmp_path, "run1", {"m": "a"}, exit_code=0)

    async def check(page: Page) -> None:
        await expect(page.get_by_text("counts rule doesn't work")).to_be_visible()

    for site in serve(tmp_path):
        browse(site, check)


def test_says_how_to_start_without_experiments(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")

    async def check(page: Page) -> None:
        await expect(page.get_by_text("No experiments found.")).to_be_visible()
        await expect(page.get_by_role("button", name="Cards")).to_have_count(0)

    for site in serve(tmp_path):
        browse(site, check)
