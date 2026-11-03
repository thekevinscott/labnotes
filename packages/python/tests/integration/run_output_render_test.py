import asyncio
from pathlib import Path

from textual.app import App, ComposeResult

from labnotes.tui.run_output import RunOutput


class OutputApp(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output")


def test_visible_line_keeps_ansi_color_and_scrolls_sideways(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("\x1b[31mred\x1b[0m plain" + "x" * 200 + "\n")

    async def drive() -> None:
        app = OutputApp()
        async with app.run_test(size=(40, 8)) as pilot:
            output = app.query_one(RunOutput)
            output.follow(tmp_path)
            await pilot.pause()
            strip = output.render_line(0)
            assert "".join(segment.text for segment in strip._segments).startswith(
                "red plain"
            )
            assert "color(1)" in str(strip._segments[0].style)
            assert output.virtual_size.height == 1
            assert output.virtual_size.width > output.size.width
            output.scroll_to(x=100, animate=False, immediate=True)
            await pilot.pause()
            assert output.scroll_offset.x > 0
            assert "x" in "".join(
                segment.text for segment in output.render_line(0)._segments
            )

    asyncio.run(drive())
