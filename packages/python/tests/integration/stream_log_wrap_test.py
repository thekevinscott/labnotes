from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from rich.console import Console
from rich.style import Style
from textual.geometry import Size
from textual.strip import Strip

from labnotes.tui.stream_log import StreamLog


@pytest.fixture
def sized() -> Iterator[None]:
    with (
        mock.patch.object(
            StreamLog, "view", new_callable=mock.PropertyMock, return_value=Size(4, 3)
        ),
        mock.patch.object(StreamLog, "scroll_to"),
    ):
        yield


def texts(strips: list[Strip]) -> list[str]:
    return [strip.text for strip in strips]


@pytest.fixture
def drawn() -> Iterator[None]:
    app = mock.Mock(console=Console(width=200, color_system="truecolor"))
    with mock.patch.multiple(
        StreamLog,
        app=mock.PropertyMock(return_value=app),
        rich_style=mock.PropertyMock(return_value=Style()),
        text_selection=mock.PropertyMock(return_value=None),
        screen=mock.PropertyMock(),
    ):
        yield


@pytest.mark.usefixtures("sized", "drawn")
def test_wraps_a_line_at_the_view_width(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("abcdefghij\n\nabcd\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    wrapped = output.wrap(0)
    assert texts(wrapped) == ["abcd", "efgh", "ij  "]
    assert [
        (strip._segments[0].style or Style()).meta["offset"] for strip in wrapped
    ] == [
        (0, 0),
        (4, 0),
        (8, 0),
    ]
    assert texts(output.wrap(1)) == ["    "]
    assert texts(output.wrap(2)) == ["abcd"]
    assert output.wrap(0) is wrapped


@pytest.mark.usefixtures("sized", "drawn")
def test_keeps_ansi_color_on_wrapped_rows(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("\x1b[31mredred\x1b[0m\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    colors = {
        segment.text: segment.style.color.name
        for strip in output.wrap(0)
        for segment in strip._segments
        if segment.style and segment.style.color and segment.text.strip()
    }
    assert colors == {"redr": "color(1)", "ed": "color(1)"}


@pytest.mark.parametrize(
    ("span", "selected"), [(None, ""), ((0, -1), "abcdef"), ((1, 5), "bcde")]
)
@pytest.mark.usefixtures("sized", "drawn")
def test_highlights_the_selected_part_of_a_line(
    tmp_path: Path, span: tuple[int, int] | None, selected: str
) -> None:
    (tmp_path / "stdout.log").write_text("abcdef\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    selection = mock.Mock()
    selection.get_span.return_value = span
    output.wrapped.clear()
    highlight = Style(reverse=True)
    screen: Any = mock.Mock()
    screen.get_component_rich_style.return_value = highlight
    with mock.patch.multiple(
        StreamLog,
        text_selection=mock.PropertyMock(return_value=selection),
        screen=mock.PropertyMock(return_value=screen),
    ):
        wrapped = output.wrap(0)
    selection.get_span.assert_called_once_with(0)
    assert selected == "".join(
        segment.text
        for strip in wrapped
        for segment in strip._segments
        if segment.style and segment.style.reverse
    )
