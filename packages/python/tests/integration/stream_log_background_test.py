import asyncio
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.geometry import Region

from labnotes.tui.run_output import RunOutput


class OutputApp(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output")


@pytest.mark.parametrize("focused", [False, True])
def test_text_rows_share_the_log_background(tmp_path: Path, focused: bool) -> None:
    (tmp_path / "stdout.log").write_text(
        "first paragraph line\n\nsecond \x1b[31mred\x1b[0m paragraph\n\nthird\n"
    )

    async def drive() -> None:
        app = OutputApp()
        async with app.run_test(size=(40, 10)) as pilot:
            app.query_one(RunOutput).follow(tmp_path)
            log = app.query_one(RunOutput).logs["stdout"]
            if focused:
                log.focus()
            await pilot.pause()
            width = log.scrollable_content_region.width
            rows = log.render_lines(Region(0, 0, width, 5))
            assert [row.text.rstrip() for row in rows] == [
                "first paragraph line",
                "",
                "second red paragraph",
                "",
                "third",
            ]
            backgrounds = {
                (y, segment.text): segment.style.bgcolor if segment.style else None
                for y, row in enumerate(rows)
                for segment in row
                if segment.text
            }
            assert len(set(backgrounds.values())) == 1, backgrounds
            assert None not in backgrounds.values()

    asyncio.run(drive())
