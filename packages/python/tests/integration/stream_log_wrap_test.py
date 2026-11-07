import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.geometry import Offset
from textual.selection import Selection
from textual.strip import Strip

from labnotes.tui.stream_log import StreamLog


class Host(App[None]):
    CSS = "StreamLog { width: 6; height: 4; }"

    def compose(self) -> ComposeResult:
        yield StreamLog("stdout", id="log")


def mounted(text: str, check: Callable[[StreamLog], None]) -> Callable[[Path], None]:
    def run(tmp_path: Path) -> None:
        (tmp_path / "stdout.log").write_text(text)

        async def drive() -> None:
            app = Host()
            async with app.run_test(size=(20, 10)) as pilot:
                log = app.query_one(StreamLog)
                log.follow(tmp_path)
                await pilot.pause()
                check(log)

        asyncio.run(drive())

    return run


def texts(strips: list[Strip]) -> list[str]:
    return [strip.text for strip in strips]


def test_wraps_a_line_at_the_view_width(tmp_path: Path) -> None:
    def check(log: StreamLog) -> None:
        assert log.view.width == 4
        wrapped = log.wrap(0)
        assert texts(wrapped) == ["abcd", "efgh", "ij  "]
        assert texts(log.wrap(1)) == ["    "]
        assert texts(log.wrap(2)) == ["abcd"]
        assert log.wrap(0) is wrapped

    mounted("abcdefghij\n\nabcd\n", check)(tmp_path)


def test_keeps_ansi_color_on_wrapped_rows(tmp_path: Path) -> None:
    def check(log: StreamLog) -> None:
        colors = {
            segment.text: segment.style.color.name
            for strip in log.wrap(0)
            for segment in strip._segments
            if segment.style and segment.style.color and segment.text.strip()
        }
        assert colors == {"redr": "color(1)", "ed": "color(1)"}

    mounted("\x1b[31mredred\x1b[0m\n", check)(tmp_path)


@pytest.mark.parametrize(
    ("selection", "selected"),
    [
        (None, ""),
        (Selection(None, None), "abcdef"),
        (Selection(Offset(1, 0), Offset(5, 0)), "bcde"),
    ],
)
def test_highlights_the_selected_part_of_a_line(
    tmp_path: Path, selection: Selection | None, selected: str
) -> None:
    def check(log: StreamLog) -> None:
        if selection is not None:
            log.screen.selections = {log: selection}
        log.selection_updated(selection)
        highlight = log.screen.get_component_rich_style("screen--selection")
        assert (
            selected
            == "".join(
                segment.text
                for strip in log.wrap(0)
                for segment in strip._segments
                if segment.style and highlight.bgcolor == segment.style.bgcolor
            ).strip()
        )

    mounted("abcdef\n", check)(tmp_path)
