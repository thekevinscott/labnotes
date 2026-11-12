import asyncio
import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Tab

from labnotes.tui.run_output import RunOutput


class OutputApp(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output")


def record(folder: Path, count: int) -> None:
    invocations = [
        {
            "started": f"2026-11-02T0{number}:00:00Z",
            "stdout": f"stdout-{number}.txt",
            "stderr": f"stderr-{number}.txt",
        }
        for number in range(1, count + 1)
    ]
    (folder / "run.json").write_text(json.dumps({"invocations": invocations}))


def screen(app: App[None]) -> list[str]:
    log = app.query_one(RunOutput).logs["stdout"]
    return [log.render_line(y).text.rstrip() for y in range(log.view.height)]


def test_output_view_labels_each_invocation_however_late_it_opens(
    tmp_path: Path,
) -> None:
    (tmp_path / "stdout-1.txt").write_text("saved step 20\n")
    (tmp_path / "stderr-1.txt").write_text("")
    record(tmp_path, 1)

    async def drive() -> None:
        watching, late = OutputApp(), OutputApp()
        async with watching.run_test(size=(60, 12)) as pilot:
            watching.query_one(RunOutput).follow(tmp_path)
            await pilot.pause()
            (tmp_path / "stdout-2.txt").write_text("resumed from step 20\n")
            (tmp_path / "stderr-2.txt").write_text("")
            record(tmp_path, 2)
            watching.query_one(RunOutput).follow(tmp_path)
            await pilot.pause()
            seen = screen(watching)
        async with late.run_test(size=(60, 12)) as pilot:
            late.query_one(RunOutput).follow(tmp_path)
            await pilot.pause()
            assert screen(late) == seen
            assert seen[:4] == [
                "── invocation 1 · 2026-11-02T01:00:00Z ──",
                "saved step 20",
                "── invocation 2 · 2026-11-02T02:00:00Z ──",
                "resumed from step 20",
            ]
            tab = late.query_one("#stdout-tab", Tab)
            assert tab.label_text == "stdout (2)"

    asyncio.run(drive())
