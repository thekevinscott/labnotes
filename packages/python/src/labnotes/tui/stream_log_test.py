import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from rich.color import Color
from rich.console import Console
from rich.style import Style

from labnotes.tui.stream_log import StreamLog


def append(path: Path, text: str) -> None:
    with path.open("a") as file:
        file.write(text)


def shown(output: StreamLog) -> list[str]:
    return output.read(0, output.rows)


@pytest.fixture
def sized() -> Iterator[mock.Mock]:
    with (
        mock.patch.object(
            StreamLog,
            "view",
            new_callable=mock.PropertyMock,
            return_value=mock.Mock(width=4, height=3),
        ),
        mock.patch.object(StreamLog, "scroll_to") as scroll,
    ):
        yield scroll


def test_starts_empty() -> None:
    output = StreamLog("stdout", id="output")
    assert (output.id, output.stream, output.segments) == ("output", "stdout", [])
    assert (output.first, output.window, output.rows, output.count) == (0, [], 0, 0)
    assert (output.pinned, output.bottom, output.wrapped) == (True, 0, {})


def test_follows_nothing_before_a_run_writes_output(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    output.follow(tmp_path)
    assert (shown(output), output.segments) == ([], [])


def test_follows_its_own_stream_only(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("out\n")
    (tmp_path / "stderr.log").write_text("oops\n")
    output = StreamLog("stderr")
    output.follow(tmp_path)
    assert shown(output) == ["oops"]
    assert [segment.path for segment in output.segments] == [tmp_path / "stderr.log"]


def test_reads_only_new_bytes_on_each_follow(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    output.follow(tmp_path)
    append(tmp_path / "stdout.log", "two\nthree\n")
    output.follow(tmp_path)
    assert shown(output) == ["one", "two", "three"]
    assert (output.segments[0].scanned, output.virtual_size.height) == (14, 3)


def test_appending_keeps_already_rendered_lines(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    rendered = mock.Mock()
    output.wrapped[0] = rendered
    append(tmp_path / "stdout.log", "two\n")
    output.follow(tmp_path)
    assert output.wrapped == {0: rendered}


def test_decodes_characters_split_across_follows(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout.log").write_bytes(b"caf\xc3")
    output.follow(tmp_path)
    with (tmp_path / "stdout.log").open("ab") as file:
        file.write(b"\xa9 done\n")
    output.follow(tmp_path)
    assert shown(output) == ["café done"]


@pytest.mark.parametrize(
    ("text", "count"),
    [("", 0), ("one", 0), ("one\n", 1), ("one\ntwo", 1), ("one\ntwo\nthree", 2)],
)
def test_counts_only_complete_lines(tmp_path: Path, text: str, count: int) -> None:
    (tmp_path / "stdout.log").write_text(text)
    output = StreamLog("stdout")
    output.follow(tmp_path)
    assert output.count == count


def test_growth_forgets_only_rows_that_can_change(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("one\ntwo\npar")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.first, output.window = 1, ["two", "par"]
    cached: dict[int, list[Any]] = {0: [], 1: [], 2: []}
    output.wrapped.update(cached)
    append(tmp_path / "stdout.log", "tial\n")
    output.follow(tmp_path)
    assert output.window == ["two"]
    assert output.wrapped == {0: [], 1: []}
    assert shown(output) == ["one", "two", "partial"]


def test_growth_before_the_window_forgets_all_of_it(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("par")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.first, output.window = 3, ["later", "later still"]
    append(tmp_path / "stdout.log", "tial\n")
    output.follow(tmp_path)
    assert output.window == []


def test_growth_retains_only_lines_before_the_changed_row(tmp_path: Path) -> None:
    log = tmp_path / "stdout.log"
    log.write_text("a\nb\nc\npartial")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.first, output.window = 2, ["c", "partial", "stale"]
    append(log, " line\n")
    output.follow(tmp_path)
    assert output.window == ["c"]


def test_growth_forgets_wrapped_rows_beyond_the_settled_count(tmp_path: Path) -> None:
    log = tmp_path / "stdout.log"
    log.write_text("x\n" * 300 + "partial")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.wrapped = {298: [], 299: [], int("300"): [], 301: []}
    append(log, " line\n")
    output.follow(tmp_path)
    assert list(output.wrapped) == [298, 299]


def test_an_unsized_view_scrolls_by_line(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("one\ntwo\n")
    output = StreamLog("stdout")
    output.shown = ("key", [])
    with mock.patch.object(StreamLog, "scroll_to") as scroll:
        output.follow(tmp_path)
    assert (output.bottom, output.virtual_size, output.shown) == (2, (0, 2), (None, []))
    scroll.assert_not_called()


@pytest.mark.parametrize(("width", "height"), [(0, 3), (4, 0), (1, 3), (4, 1)])
def test_settle_handles_each_view_dimension_at_its_boundary(
    tmp_path: Path, width: int, height: int
) -> None:
    (tmp_path / "stdout.log").write_text("one\ntwo\n")
    output = StreamLog("stdout")
    with (
        mock.patch.object(
            StreamLog,
            "view",
            new_callable=mock.PropertyMock,
            return_value=mock.Mock(width=width, height=height),
        ),
        mock.patch.object(StreamLog, "wrap", return_value=[mock.Mock()]) as wrap,
        mock.patch.object(StreamLog, "scroll_to") as scroll,
    ):
        output.follow(tmp_path)
    if width == 0 or height == 0:
        assert (output.bottom, output.virtual_size) == (2, (0, 2))
        wrap.assert_not_called()
        scroll.assert_not_called()
    else:
        expected = (1, (0, 2)) if height == 1 else (0, (0, 3))
        assert (output.bottom, output.virtual_size) == expected
        scroll.assert_called_once()


@pytest.mark.parametrize(
    ("rows", "bottom", "pinned"),
    [([1, 1], 0, True), ([1, 1, 1, 1], 1, True), ([1, 1, 2, 2], 2, False)],
)
def test_the_scroll_range_lets_the_last_line_reach_the_bottom(
    tmp_path: Path, sized: mock.Mock, rows: list[int], bottom: int, pinned: bool
) -> None:
    (tmp_path / "stdout.log").write_text("x\n" * len(rows))
    output = StreamLog("stdout")
    output.pinned = pinned
    with mock.patch.object(
        StreamLog, "wrap", side_effect=lambda line: [mock.Mock()] * rows[line]
    ):
        output.follow(tmp_path)
    assert (output.bottom, output.virtual_size) == (bottom, (0, bottom + 3))
    if pinned:
        sized.assert_called_once_with(y=bottom, animate=False, immediate=True)
    else:
        sized.assert_not_called()


def test_a_resize_rewraps_every_line() -> None:
    output = StreamLog("stdout")
    output.wrapped[0] = []
    with mock.patch.object(StreamLog, "settle") as settle:
        output.on_resize(mock.Mock())
    assert output.wrapped == {}
    settle.assert_called_once_with()


@pytest.mark.parametrize(("y", "pinned"), [(4, False), (5, True), (6, True)])
def test_scrolling_to_the_bottom_pins_the_view(y: int, pinned: bool) -> None:
    output = StreamLog("stdout")
    output.bottom = 5
    output.pinned = not pinned
    output.watch_scroll_y(0, y)
    assert output.pinned is pinned


def test_a_new_selection_redraws_every_line() -> None:
    output = StreamLog("stdout")
    output.wrapped[0], output.shown = [], ("key", [])
    with mock.patch.object(StreamLog, "refresh") as refresh:
        output.selection_updated(None)
    assert (output.wrapped, output.shown) == ({}, (None, []))
    refresh.assert_called_once_with()


def test_loads_the_lines_around_one_outside_the_window(
    tmp_path: Path, sized: mock.Mock
) -> None:
    (tmp_path / "stdout.log").write_text("".join(f"{n}\n" for n in range(500)))
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    output.wrapped = {0: [], 150: [], 300: [], 497: [], 499: []}
    assert output.line(250) == "250"
    assert (output.first, len(output.window)) == (150, 203)
    assert list(output.wrapped) == [150, 300, 497, 499]
    assert output.line(0) == "0"
    assert (output.first, len(output.window)) == (0, 203)
    output.window = ["kept"]
    assert output.line(0) == "kept"


def test_a_line_inside_the_window_does_not_reload_it(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("".join(f"{n}\n" for n in range(500)))
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    with mock.patch.object(output, "read", wraps=output.read) as read:
        assert output.line(250) == "250"
        assert output.line(251) == "251"
        assert output.line(250) == "250"
    read.assert_called_once_with(150, 200)


def test_window_boundary_and_tail_cache_do_not_use_bitwise_ranges(
    tmp_path: Path,
) -> None:
    (tmp_path / "stdout.log").write_text("".join(f"{n}\n" for n in range(500)))
    output = StreamLog("stdout")
    with (
        mock.patch.object(StreamLog, "settle"),
        mock.patch.object(
            StreamLog,
            "view",
            new_callable=mock.PropertyMock,
            return_value=mock.Mock(width=4, height=8),
        ),
    ):
        output.follow(tmp_path)
        output.wrapped = {
            149: [],
            150: [],
            300: [],
            357: [],
            358: [],
            400: [],
            491: [],
            492: [],
        }
        assert output.line(250) == "250"
        assert (output.first, len(output.window)) == (150, 208)
        assert list(output.wrapped) == [150, 300, 357, 492]
        assert output.line(358) == "358"
        assert (output.first, len(output.window)) == (258, 208)


def test_count_uses_the_newest_segment_lines(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    first.write_text("x\n" * 3)
    second.write_text("last\npartial")
    with mock.patch("labnotes.tui.stream_log.latest_log", side_effect=[first, second]):
        output.follow(tmp_path)
        output.follow(tmp_path)
    assert (output.rows, output.count) == (5, 4)


def test_read_limits_the_second_segment_to_the_remaining_count(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    first.write_text("a\nb\n")
    second.write_text("c\nd\ne\nf\n")
    with mock.patch("labnotes.tui.stream_log.latest_log", side_effect=[first, second]):
        output.follow(tmp_path)
        output.follow(tmp_path)
    assert output.read(1, 2) == ["b", "c"]
    assert output.read(1, 3) == ["b", "c", "d"]
    assert output.read(3, 2) == ["d", "e"]


def test_read_skips_a_large_completed_segment(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    first.write_text("x\n" * 300)
    second.write_text("a\nb\nc\n")
    with mock.patch("labnotes.tui.stream_log.latest_log", side_effect=[first, second]):
        output.follow(tmp_path)
        output.follow(tmp_path)
    assert output.read(301, 1) == ["b"]
    with mock.patch.object(
        output.segments[0], "read", wraps=output.segments[0].read
    ) as read:
        assert output.read(300, 1) == ["a"]
    read.assert_not_called()


def test_a_newer_segment_truncated_below_its_scanned_size_resets_all(
    tmp_path: Path,
) -> None:
    output = StreamLog("stdout")
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    first.write_text("first\n")
    second.write_text("long second line\n")
    with mock.patch(
        "labnotes.tui.stream_log.latest_log", side_effect=[first, second, second]
    ):
        output.follow(tmp_path)
        output.follow(tmp_path)
        second.write_text("new\n")
        output.follow(tmp_path)
    assert shown(output) == ["new"]
    assert len(output.segments) == 1


@pytest.fixture
def drawing() -> Iterator[dict[str, Any]]:
    with mock.patch.multiple(
        "labnotes.tui.stream_log",
        Text=mock.DEFAULT,
        Strip=mock.DEFAULT,
        cell_len=mock.DEFAULT,
    ) as patched:
        with mock.patch.multiple(
            StreamLog,
            app=mock.PropertyMock(),
            rich_style=mock.PropertyMock(),
            text_selection=mock.PropertyMock(return_value=None),
            screen=mock.PropertyMock(),
        ):
            yield patched


def piece(*texts: str) -> mock.MagicMock:
    strip = mock.MagicMock()
    strip.__iter__.return_value = [mock.Mock(text=text) for text in texts]
    return strip


@pytest.mark.parametrize(("length", "cuts"), [(10, [4, 8, 10]), (4, [4]), (5, [4, 5])])
@pytest.mark.usefixtures("sized")
def test_cuts_a_line_into_rows_of_the_view_width(
    tmp_path: Path, drawing: dict[str, Any], length: int, cuts: list[int]
) -> None:
    (tmp_path / "stdout.log").write_text("line\n")
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    strip = drawing["Strip"].return_value.apply_style.return_value
    strip.cell_length = length
    pieces = [piece("ab", "cd"), piece("e")]
    strip.divide.return_value = pieces
    wrapped = output.wrap(0)
    text = drawing["Text"].from_ansi.return_value
    drawing["Text"].from_ansi.assert_called_once_with("line", style=output.rich_style)
    drawing["Strip"].assert_called_once_with(
        text.render.return_value, drawing["cell_len"].return_value
    )
    drawing["Strip"].return_value.apply_style.assert_called_once_with(output.rich_style)
    strip.divide.assert_called_once_with(cuts)
    for each in pieces:
        each.extend_cell_length.assert_called_once_with(4, output.rich_style)
    assert [
        each.extend_cell_length.return_value.apply_offsets.call_args for each in pieces
    ] == [
        mock.call(0, 0),
        mock.call(4, 0),
    ]
    assert wrapped == [
        each.extend_cell_length.return_value.apply_offsets.return_value
        for each in pieces
    ]
    assert output.wrap(0) is wrapped
    assert output.wrapped == {0: wrapped}


@pytest.mark.usefixtures("sized")
def test_an_empty_line_takes_one_row(tmp_path: Path, drawing: dict[str, Any]) -> None:
    (tmp_path / "stdout.log").write_text("\n")
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    strip = drawing["Strip"].return_value.apply_style.return_value
    strip.cell_length = 0
    strip.__iter__.return_value = []
    wrapped = output.wrap(0)
    strip.divide.assert_not_called()
    assert wrapped == [strip.extend_cell_length.return_value.apply_offsets.return_value]


@pytest.mark.parametrize("span", [None, (0, -1), (0, 0), (1, 2)])
@pytest.mark.usefixtures("sized")
def test_highlights_the_selected_part_of_a_line(
    tmp_path: Path, drawing: dict[str, Any], span: tuple[int, int] | None
) -> None:
    (tmp_path / "stdout.log").write_text("red\n")
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    drawing["Strip"].return_value.apply_style.return_value.cell_length = 0
    text = drawing["Text"].from_ansi.return_value
    text.__len__ = mock.Mock(return_value=3)
    selection = mock.Mock()
    selection.get_span.return_value = span
    with mock.patch.object(
        StreamLog,
        "text_selection",
        new_callable=mock.PropertyMock,
        return_value=selection,
    ):
        output.wrap(0)
        screen: Any = output.screen
    selection.get_span.assert_called_once_with(0)
    if span is None:
        text.stylize.assert_not_called()
    else:
        text.stylize.assert_called_once_with(
            screen.get_component_rich_style.return_value,
            span[0],
            3 if span[1] == -1 else span[1],
        )


@pytest.mark.parametrize(
    ("top", "bottom", "rows"),
    [
        (0, 3, ["0a", "0b", "1a"]),
        (1, 3, ["1a", "2a", "2b"]),
        (3, 3, ["4a", "4b", "5a"]),
    ],
)
def test_fills_the_view_from_the_top_line_or_against_the_bottom(
    tmp_path: Path, sized: mock.Mock, top: int, bottom: int, rows: list[str]
) -> None:
    (tmp_path / "stdout.log").write_text("x\n" * 6)
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    output.bottom = bottom
    pieces = {line: [f"{line}a", f"{line}b"][: 2 - line % 2] for line in range(6)}
    with (
        mock.patch.object(
            StreamLog, "scroll_y", new_callable=mock.PropertyMock, return_value=top
        ),
        mock.patch.object(
            StreamLog, "wrap", side_effect=lambda line: pieces[line]
        ) as wrap,
    ):
        first = output.screen_rows()
        assert first == rows
        calls = wrap.call_count
        assert output.screen_rows() is first
        assert wrap.call_count == calls


@pytest.mark.usefixtures("sized")
def test_screen_rows_stop_reading_when_the_view_is_full(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("x\n" * 6)
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    output.bottom = 4
    with (
        mock.patch.object(
            StreamLog, "scroll_y", new_callable=mock.PropertyMock, return_value=0
        ),
        mock.patch.object(StreamLog, "wrap", return_value=["row"]) as wrap,
    ):
        assert output.screen_rows() == ["row"] * 3
    assert wrap.call_count == 3


@pytest.mark.usefixtures("sized")
def test_screen_rows_stop_after_a_wrapped_line_fills_the_view(
    tmp_path: Path,
) -> None:
    (tmp_path / "stdout.log").write_text("x\n" * 6)
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    output.bottom = 4
    with (
        mock.patch.object(
            StreamLog, "scroll_y", new_callable=mock.PropertyMock, return_value=0
        ),
        mock.patch.object(StreamLog, "wrap", return_value=["a", "b"]) as wrap,
    ):
        assert output.screen_rows() == ["a", "b", "a"]
    assert wrap.call_count == 2


@pytest.mark.parametrize("top", [6, 7])
@pytest.mark.usefixtures("sized")
def test_screen_rows_handle_scrolling_past_the_last_row(
    tmp_path: Path, top: int
) -> None:
    (tmp_path / "stdout.log").write_text("x\n" * 6)
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    output.bottom = 3
    with (
        mock.patch.object(
            StreamLog, "scroll_y", new_callable=mock.PropertyMock, return_value=top
        ),
        mock.patch.object(
            StreamLog, "wrap", side_effect=AssertionError("read past end")
        ) as wrap,
    ):
        assert output.screen_rows() == []
    wrap.assert_not_called()


@pytest.mark.parametrize(("top", "calls"), [(300.0, 10), (301.0, 9)])
@pytest.mark.usefixtures("sized")
def test_screen_rows_bottom_alignment_uses_value_equality_for_large_lines(
    tmp_path: Path, top: float, calls: int
) -> None:
    (tmp_path / "stdout.log").write_text("x\n" * 310)
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "settle"):
        output.follow(tmp_path)
    output.bottom = int("300")

    def wraps(line: int) -> list[str]:
        assert line < 310
        return [str(line)] * 2

    with (
        mock.patch.object(
            StreamLog, "scroll_y", new_callable=mock.PropertyMock, return_value=top
        ),
        mock.patch.object(StreamLog, "wrap", side_effect=wraps) as wrap,
    ):
        assert output.screen_rows() == ["308", "309", "309"]
    assert wrap.call_count == calls


def test_reset_starts_over_for_another_folder(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("old\npartial")
    (tmp_path / "r2" / "stdout.log").write_text("hi\n")
    output = StreamLog("stdout")
    output.follow(tmp_path / "r1")
    output.first, output.window, output.bottom = 1, ["partial"], 2
    output.wrapped[0] = []
    output.shown = ("key", [])
    output.reset()
    assert (output.segments, output.first, output.window) == ([], 0, [])
    assert (output.wrapped, output.shown, output.bottom) == ({}, (None, []), 0)
    assert output.virtual_size == (0, 0)
    output.follow(tmp_path / "r2")
    assert shown(output) == ["hi"]


def test_keeps_earlier_invocations_above_the_newest(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout-20261102-090000-000000.txt").write_text("first\npar")
    (tmp_path / "run.json").write_text(
        json.dumps({"invocations": [{"stdout": "stdout-20261102-090000-000000.txt"}]})
    )
    output.follow(tmp_path)
    output.first, output.window = 0, ["first", "par"]
    (tmp_path / "stdout-20261102-100000-000000.txt").write_text("next\n")
    (tmp_path / "run.json").write_text(
        json.dumps({"invocations": [{"stdout": "stdout-20261102-100000-000000.txt"}]})
    )
    output.follow(tmp_path)
    output.follow(tmp_path)
    assert shown(output) == ["first", "par", "next"]
    assert output.window == ["first", "par"]
    assert (output.rows, output.count) == (3, 3)
    assert output.read(1, 2) == ["par", "next"]
    assert output.read(2, 5) == ["next"]


def test_switches_to_a_log_path_that_sorts_before_the_previous_one(
    tmp_path: Path,
) -> None:
    older_name = tmp_path / "z.log"
    newer_name = tmp_path / "a.log"
    older_name.write_text("first line\n")
    newer_name.write_text("new\n")
    output = StreamLog("stdout")
    with mock.patch(
        "labnotes.tui.stream_log.latest_log",
        side_effect=[older_name, newer_name],
    ):
        output.follow(tmp_path)
        output.follow(tmp_path)
    assert shown(output) == ["first line", "new"]


def test_rereads_a_log_that_was_truncated(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    log = tmp_path / "stdout.log"
    log.write_text("first line\nsecond\n")
    output.follow(tmp_path)
    log.write_text("new\n")
    output.follow(tmp_path)
    assert shown(output) == ["new"]
    assert output.segments[0].scanned == 4


def test_a_deleted_log_clears_the_view(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    log = tmp_path / "stdout.log"
    log.write_text("first line\n")
    output.follow(tmp_path)
    log.unlink()
    output.follow(tmp_path)
    assert (shown(output), output.segments) == ([], [])
    log.write_text("again\n")
    output.follow(tmp_path)
    assert shown(output) == ["again"]


def test_a_rewritten_log_of_the_same_size_is_followed_on(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    output.follow(tmp_path)
    assert len(output.segments) == 1


@pytest.mark.usefixtures("sized")
def test_renders_a_screen_row_or_a_blank_past_the_last() -> None:
    output = StreamLog("stdout")
    row = mock.Mock()
    with (
        mock.patch.object(StreamLog, "screen_rows", return_value=[row]),
        mock.patch.object(StreamLog, "rich_style", new_callable=mock.PropertyMock),
        mock.patch("labnotes.tui.stream_log.Strip") as strip,
    ):
        assert output.render_line(0) is row
        assert output.render_line(1) is strip.blank.return_value
        strip.blank.assert_called_once_with(4, output.rich_style)


@pytest.mark.usefixtures("sized")
def test_text_takes_the_log_background_unless_it_sets_its_own(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("ab\n\x1b[41mc\x1b[0md\n")
    output = StreamLog("stdout")
    base = Style(color="white", bgcolor="#1e1e1e")
    with (
        mock.patch.multiple(
            StreamLog,
            app=mock.PropertyMock(return_value=mock.Mock(console=Console())),
            rich_style=mock.PropertyMock(return_value=base),
            text_selection=mock.PropertyMock(return_value=None),
        ),
        mock.patch.object(StreamLog, "settle"),
    ):
        output.follow(tmp_path)
        rows = [output.wrap(0)[0], output.wrap(1)[0]]
    assert [
        [(cell.text, cell.style and cell.style.bgcolor) for cell in row] for row in rows
    ] == [
        [("ab", base.bgcolor), ("  ", base.bgcolor)],
        [("c", Color.parse("color(1)")), ("d", base.bgcolor), ("  ", base.bgcolor)],
    ]
