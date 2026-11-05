import asyncio
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult

from labnotes.tui.hook_panel import HookPanel


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield HookPanel("setup", id="panel")


def header(panel: HookPanel) -> str:
    widget: Any = panel.query_one(".hook-header")
    return str(widget.content)


def check(steps: Any) -> None:
    async def drive() -> None:
        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            steps(app.query_one(HookPanel))

    asyncio.run(drive())


def test_waits_until_the_hook_starts() -> None:
    def steps(panel: HookPanel) -> None:
        assert panel.state == "waiting"
        assert header(panel) == "setup: waiting"

    check(steps)


def test_shows_the_elapsed_time_and_outcome(tmp_path: Path) -> None:
    def steps(panel: HookPanel) -> None:
        panel.start(tmp_path, 100.0)
        assert panel.state == "running"
        panel.end(None, 165.0)
        assert panel.state == "passed"
        assert header(panel) == "setup: ✓  1m 05s"

    check(steps)


def test_shows_the_error_of_a_failed_hook(tmp_path: Path) -> None:
    def steps(panel: HookPanel) -> None:
        panel.start(tmp_path, 100.0)
        panel.end("setup command up exited 3", 102.0)
        assert panel.state == "failed"
        assert header(panel) == "setup: ✗ setup command up exited 3  2s"

    check(steps)


def test_follows_the_hooks_logs(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("pod ready\n")

    def steps(panel: HookPanel) -> None:
        panel.start(tmp_path, 100.0)
        panel.follow()
        assert "pod ready" in panel.query_one("#setup-output").lines  # type: ignore[attr-defined]

    check(steps)
