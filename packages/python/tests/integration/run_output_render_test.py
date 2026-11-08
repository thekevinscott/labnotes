import asyncio
from pathlib import Path

from textual.app import App, ComposeResult

from labnotes.tui.run_output import RunOutput


class OutputApp(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output")


def test_visible_line_keeps_ansi_color_and_wraps(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("\x1b[31mred\x1b[0m plain" + "x" * 200 + "\n")

    async def drive() -> None:
        app = OutputApp()
        async with app.run_test(size=(40, 8)) as pilot:
            app.query_one(RunOutput).follow(tmp_path)
            output = app.query_one(RunOutput).logs["stdout"]
            await pilot.pause()
            strip = output.render_line(0)
            assert "".join(segment.text for segment in strip._segments).startswith(
                "red plain"
            )
            assert "color(1)" in str(strip._segments[0].style)
            width = output.scrollable_content_region.width
            assert len(output.wrap(0)) == -(-209 // width)
            assert output.virtual_size.width <= width
            assert not output.show_horizontal_scrollbar

    asyncio.run(drive())
