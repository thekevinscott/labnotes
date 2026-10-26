import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psutil
from playwright.async_api import Page, expect
from conftest import browse, daemon, run, serve, write


def test_shows_the_experiment_toml_on_one_line(site: str) -> None:
    async def check(page: Page) -> None:
        await expect(page.get_by_role("heading", name="Alpha study")).to_be_visible()
        summary = page.locator(".config-summary")
        await expect(summary).to_contain_text("matrix")
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


def test_lists_runs_in_a_table(site: str) -> None:
    async def check(page: Page) -> None:
        await expect(page.get_by_role("link", name="Runs 2")).to_have_attribute(
            "aria-current", "page"
        )
        table = page.get_by_role("table")
        header = table.get_by_role("columnheader", name="source-language")
        await expect(header).to_be_visible()
        await expect(table.get_by_role("row").filter(has_text="run2")).to_have_count(1)

    browse(f"{site}/experiments/alpha", check)


def test_shows_when_each_run_started_and_how_long_it_took(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'command = "true"\n')
    run(tmp_path, "run1", {}, exit_code=0, ended="2026-10-17T00:08:21Z")
    run(tmp_path, "run2", {})

    async def check(page: Page) -> None:
        table = page.get_by_role("table")
        for column in ("started", "duration"):
            await expect(table.get_by_role("columnheader", name=column)).to_be_visible()
        done = table.get_by_role("row").filter(has_text="run1")
        await expect(done).to_contain_text("2026-10-16 20:00:01")
        await expect(done).to_contain_text("8m 20s")
        await expect(table.get_by_role("row").filter(has_text="run2")).to_contain_text(
            "—"
        )

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check, timezone_id="America/New_York")


def test_filters_runs_by_text(site: str) -> None:
    async def check(page: Page) -> None:
        await page.get_by_label("Filter id").fill("2")
        await page.get_by_label("Filter id").press("Enter")

        await expect(page.get_by_role("cell", name="run2", exact=True)).to_be_visible()
        await expect(page.get_by_role("cell", name="run1", exact=True)).to_have_count(0)

    browse(f"{site}/experiments/alpha", check)


def test_filters_runs_live_while_typing(site: str) -> None:
    async def check(page: Page) -> None:
        box = page.get_by_label("Filter id")
        await box.press_sequentially("n2")

        await expect(page.get_by_role("cell", name="run1", exact=True)).to_have_count(0)
        await expect(page).to_have_url(re.compile(r"\?f\.id=n2$"))
        await expect(box).to_be_focused()
        assert await box.evaluate("box => box.selectionStart") == 2

        await box.press_sequentially("x")

        await expect(page.get_by_text("No runs match these filters.")).to_be_visible()
        await expect(page.get_by_text("0 of 2")).to_be_visible()

    browse(f"{site}/experiments/alpha", check)


def test_sorts_runs_in_place(site: str) -> None:
    async def check(page: Page) -> None:
        loads: list[Page] = []
        page.on("load", lambda loaded: loads.append(loaded))
        await page.evaluate("window.stayed = true")
        await page.get_by_label("Filter source-language").click()
        await page.get_by_role("checkbox", name="fr").check()
        await page.get_by_role("checkbox", name="en").check()
        await page.get_by_role("heading", name="Alpha study").click()
        rows = page.locator("tbody tr.run-row")
        header = page.get_by_role("columnheader", name="id")
        sort = header.get_by_role("link")

        await sort.click()
        await expect(header).to_have_attribute("aria-sort", "ascending")
        await sort.click()

        await expect(header).to_have_attribute("aria-sort", "descending")
        await expect(rows.first).to_contain_text("run2")
        await expect(rows.last).to_contain_text("run1")
        await expect(page).to_have_url(re.compile(r"sort=id&order=desc"))
        await expect(sort).to_be_focused()
        await expect(page.get_by_label("Filter source-language")).to_have_text("en, fr")
        assert await page.evaluate("window.stayed")
        assert loads == []

        await page.get_by_label("Filter id").fill("run")
        await page.get_by_label("Filter id").press("Enter")
        await expect(page).to_have_url(re.compile(r"sort=id&order=desc&.*f\.id=run"))
        await expect(rows.first).to_contain_text("run2")

    browse(f"{site}/experiments/alpha", check)


def test_picks_any_of_a_params_values(site: str) -> None:
    async def check(page: Page) -> None:
        picker = page.get_by_label("Filter source-language")
        run1 = page.get_by_role("cell", name="run1", exact=True)
        run2 = page.get_by_role("cell", name="run2", exact=True)
        await picker.click()
        await page.get_by_role("checkbox", name="fr").check()

        await expect(run1).to_have_count(0)
        await expect(picker).to_have_text("fr")
        await expect(page).to_have_url(re.compile(r"\?f\.source-language=fr$"))

        await page.get_by_role("checkbox", name="en").check()

        await expect(run1).to_be_visible()
        await expect(run2).to_be_visible()
        await expect(page.get_by_text("2 of 2")).to_be_visible()

        await page.get_by_role("checkbox", name="fr").uncheck()
        await page.get_by_role("heading", name="Alpha study").click()

        await expect(run2).to_have_count(0)
        await expect(page.get_by_role("checkbox", name="en")).to_be_hidden()
        await page.reload()
        await expect(picker).to_have_text("en")
        await expect(run2).to_have_count(0)

    browse(f"{site}/experiments/alpha", check)


def test_offers_no_filter_for_a_param_with_one_value(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/experiment.toml",
        'command = "go"\n[params]\nm = ["a", "b"]\nk = "same"\nj = ["one"]\n',
    )
    run(tmp_path, "run1", {"m": "a", "k": "same", "j": "one"}, exit_code=0)

    async def check(page: Page) -> None:
        table = page.get_by_role("table")
        for column in ("k", "j"):
            await expect(table.get_by_role("columnheader", name=column)).to_be_visible()
            await expect(page.get_by_label(f"Filter {column}")).to_have_count(0)
        await expect(page.get_by_label("Filter m")).to_be_visible()

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


ADHOC = 'command = "go"\nmode = "adhoc"\n[params]\nm = ["a", "b"]\n'
LAKE = "20261020-105052-lake"
POND = "20261019-090000-pond"


def unfinished(tmp_path: Path, **fields: object) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", 'command = "true"\n')
    started = datetime.now(UTC) - timedelta(seconds=5)
    run(tmp_path, "run1", {}, created=started.strftime("%Y-%m-%dT%H:%M:%SZ"), **fields)


def test_shows_an_unfinished_run_as_running_while_the_daemon_is_up(
    tmp_path: Path,
) -> None:
    # A live process, so the daemon doesn't end the run as lost.
    me = psutil.Process()
    unfinished(tmp_path, pid=me.pid, pid_created=me.create_time())

    async def check(page: Page) -> None:
        row = page.get_by_role("row").filter(has_text="run1")
        await expect(row.get_by_title("running")).to_be_visible()
        await expect(row.get_by_title("not complete")).to_have_count(0)
        elapsed = row.locator(".elapsed")
        await expect(elapsed).to_have_text(re.compile(r"^\d+s$"))
        first = await elapsed.text_content()
        await expect(elapsed).not_to_have_text(str(first), timeout=3000)

    for _ in daemon(tmp_path):
        for site in serve(tmp_path):
            browse(f"{site}/experiments/alpha", check)


def test_shows_an_unfinished_run_as_interrupted_without_a_daemon(
    tmp_path: Path,
) -> None:
    unfinished(tmp_path)

    async def check(page: Page) -> None:
        row = page.get_by_role("row").filter(has_text="run1")
        await expect(row.get_by_title("interrupted")).to_be_visible()
        await expect(row.locator(".elapsed")).to_have_count(0)

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_groups_adhoc_runs_by_invocation(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", ADHOC)
    run(tmp_path, f"{LAKE}/one1", {"m": "a"}, exit_code=0)
    run(tmp_path, f"{LAKE}/two2", {"m": "b"}, exit_code=1)
    run(tmp_path, f"{POND}/three3", {"m": "a"}, exit_code=0)

    async def check(page: Page) -> None:
        groups = page.locator(".group-row")
        one = page.get_by_role("cell", name="one1", exact=True)
        await expect(groups).to_have_count(2)
        await expect(groups.first).to_contain_text(LAKE)
        await expect(groups.first).to_contain_text("2026-10-20 06:50:52")
        await expect(
            groups.first.get_by_role("cell", name="2", exact=True)
        ).to_be_visible()
        await expect(groups.first).to_contain_text("1✓ 1✕")
        await expect(groups.last).to_contain_text(POND)
        await expect(one).to_be_hidden()

        await page.get_by_role("button", name=LAKE).click()

        await expect(one).to_be_visible()
        await expect(page.get_by_role("cell", name="three3", exact=True)).to_be_hidden()

        await page.get_by_label("Filter m").click()
        await page.get_by_role("checkbox", name="b").check()

        await expect(one).to_have_count(0)
        await expect(page.get_by_role("cell", name="two2", exact=True)).to_be_visible()
        await expect(groups).to_have_count(1)
        await expect(groups.first).to_contain_text("2026-10-20 06:50:52")
        await expect(page.get_by_role("row").filter(has_text="two2")).to_contain_text(
            "2026-10-16 20:00:02"
        )

        await groups.first.click()

        await expect(page.get_by_role("cell", name="two2", exact=True)).to_be_hidden()

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check, timezone_id="America/New_York")


def test_opens_groups_to_show_what_a_filter_matched(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", ADHOC)
    run(tmp_path, f"{LAKE}/one1", {"m": "a"}, exit_code=0)
    run(tmp_path, f"{LAKE}/two2", {"m": "b"}, exit_code=0)
    run(tmp_path, f"{POND}/three3", {"m": "a"}, exit_code=0)
    run(tmp_path, f"{POND}/four4", {"m": "a"}, exit_code=0)

    async def check(page: Page) -> None:
        lake = page.locator(".group-row").filter(has_text=LAKE)
        pond = page.locator(".group-row").filter(has_text=POND)
        one = page.get_by_role("cell", name="one1", exact=True)
        three = page.get_by_role("cell", name="three3", exact=True)
        await expect(lake.get_by_role("cell").nth(3)).to_have_text("")
        await expect(pond.get_by_role("cell").nth(3)).to_have_text("a")
        await page.get_by_role("button", name=POND).click()

        await page.get_by_label("Filter m").click()
        await page.get_by_role("checkbox", name="a").check()

        await expect(one).to_be_visible()
        await expect(lake.get_by_role("cell").nth(2)).to_have_text("1 of 2")
        await expect(lake.get_by_role("cell").nth(3)).to_have_text("a")
        await expect(pond.get_by_role("cell").nth(2)).to_have_text("2 of 2")

        await page.get_by_role("checkbox", name="a").uncheck()

        await expect(lake.get_by_role("cell").nth(2)).to_have_text("2")
        await expect(one).to_be_hidden()
        await expect(three).to_be_visible()

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_lists_adhoc_runs_flat_when_each_invocation_ran_once(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", ADHOC)
    run(tmp_path, f"{LAKE}/one1", {"m": "a"}, exit_code=0)
    run(tmp_path, f"{POND}/three3", {"m": "b"}, exit_code=0)

    async def check(page: Page) -> None:
        await expect(page.get_by_role("cell", name=f"{LAKE}/one1")).to_be_visible()
        await expect(page.locator(".group-row")).to_have_count(0)

        await page.get_by_label("Filter id").fill("three")

        await expect(page.get_by_role("cell", name=f"{LAKE}/one1")).to_have_count(0)
        await expect(page.locator(".group-row")).to_have_count(0)

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


HERON = "20261021-080000-heron"


def test_lists_a_lone_flat_adhoc_run_as_a_plain_row(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", ADHOC)
    run(tmp_path, f"{LAKE}/one1", {"m": "a"}, exit_code=0)
    run(tmp_path, f"{LAKE}/two2", {"m": "b"}, exit_code=0)
    run(tmp_path, f"{POND}/three3", {"m": "a"}, exit_code=0)
    run(tmp_path, HERON, {"m": "b"}, exit_code=0, created="2026-10-21T08:00:00Z")

    async def check(page: Page) -> None:
        groups = page.locator(".group-row")
        heron = page.get_by_role("row").filter(has_text=HERON)
        await expect(groups).to_have_count(2)
        await expect(groups.filter(has_text=HERON)).to_have_count(0)
        await expect(heron).to_have_count(1)
        await expect(heron).to_be_visible()
        await expect(heron).to_contain_text("b")
        await expect(page.locator("tbody").first).to_contain_text(HERON)
        await expect(page.get_by_role("cell", name="one1", exact=True)).to_be_hidden()

        await page.get_by_label("Filter m").click()
        await page.get_by_role("checkbox", name="a").check()

        await expect(heron).to_have_count(0)
        await expect(groups).to_have_count(2)

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_lists_flat_adhoc_runs_without_groups(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "alpha/experiment.toml", ADHOC)
    run(tmp_path, HERON, {"m": "a"}, exit_code=0, created="2026-10-21T08:00:00Z")
    run(tmp_path, f"{POND}/three3", {"m": "b"}, exit_code=0)

    async def check(page: Page) -> None:
        await expect(page.get_by_role("cell", name=HERON, exact=True)).to_be_visible()
        await expect(page.get_by_role("cell", name=f"{POND}/three3")).to_be_visible()
        await expect(page.locator(".group-row")).to_have_count(0)

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha", check)


def test_switches_between_notebooks(site: str) -> None:
    async def check(page: Page) -> None:
        await page.get_by_role("link", name="Notebooks 2").click()
        await expect(page.get_by_text("The plan")).to_be_visible()
        await expect(page.get_by_role("table")).to_have_count(0)

        await page.get_by_role("link", name="results.md").click()

        await expect(page.get_by_text("Results", exact=True)).to_be_visible()
        await expect(page.get_by_text("The plan")).to_have_count(0)
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


def test_switches_matrix_runs_to_a_grid_and_back(site: str) -> None:
    async def check(page: Page) -> None:
        toggle = page.get_by_role("navigation", name="Runs view")
        await expect(toggle.get_by_role("link", name="Table")).to_have_attribute(
            "aria-current", "page"
        )
        await toggle.get_by_role("link", name="Grid").click()

        grid = page.locator(".runs-grid")
        await expect(
            grid.get_by_role("columnheader", name="source-language")
        ).to_be_visible()
        cells = grid.locator(".grid-cell")
        await expect(cells).to_have_text(["1/2", "0/2"])
        await expect(page.locator(".runs-table")).to_have_count(0)

        await cells.nth(1).get_by_role("link").click()

        await expect(page.locator(".runs-table")).to_be_visible()
        await expect(page.get_by_label("Filter source-language")).to_have_text("fr")
        await expect(page.get_by_role("cell", name="run1", exact=True)).to_have_count(0)

    browse(f"{site}/experiments/alpha", check)


def test_offers_no_grid_for_adhoc_runs(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/experiment.toml",
        'command = "go"\nmode = "adhoc"\n[params]\nx = [1, 2]\n',
    )
    run(tmp_path, "run1", {"x": 1}, exit_code=0)

    async def check(page: Page) -> None:
        await expect(page.locator(".runs-table")).to_be_visible()
        await expect(page.get_by_role("navigation", name="Runs view")).to_have_count(0)

    for site in serve(tmp_path):
        browse(f"{site}/experiments/alpha?view=grid", check)
