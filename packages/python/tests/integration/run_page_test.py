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
