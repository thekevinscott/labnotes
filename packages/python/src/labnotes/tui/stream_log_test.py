import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.stream_log import StreamLog


def append(path: Path, text: str) -> None:
    with path.open("a") as file:
        file.write(text)


def shown(output: StreamLog) -> list[str]:
    return output.read(0, output.rows)


@pytest.fixture
def sized() -> Iterator[mock.Mock]:
    with (
        mock.patch.object(StreamLog, "size", new_callable=mock.PropertyMock) as size,
        mock.patch.object(
            StreamLog, "call_after_refresh", side_effect=lambda call: call()
        ),
    ):
        size.return_value = mock.Mock(width=10, height=5)
        yield size


def test_starts_empty() -> None:
    output = StreamLog("stdout", id="output")
    assert (output.id, output.stream, output.segments) == ("output", "stdout", [])
    assert (output.first, output.window, output.rows, output.count) == (0, [], 0, 0)
    assert output.auto_scroll


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
    output._line_cache[0] = rendered
    append(tmp_path / "stdout.log", "two\n")
    output.follow(tmp_path)
    assert output._line_cache == {0: rendered}


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
    cached = {0: mock.Mock(), 1: mock.Mock(), 2: mock.Mock()}
    output._line_cache.update(cached)
    append(tmp_path / "stdout.log", "tial\n")
    output.follow(tmp_path)
    assert output.window == ["two"]
    assert output._line_cache == {0: cached[0], 1: cached[1]}
    assert shown(output) == ["one", "two", "partial"]


def test_growth_before_the_window_forgets_all_of_it(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("par")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.first, output.window = 3, ["later"]
    append(tmp_path / "stdout.log", "tial\n")
    output.follow(tmp_path)
    assert output.window == []


@pytest.mark.parametrize(
    ("auto_scroll", "at_end", "scrolls"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_scrolls_to_the_newest_line_only_from_the_end(
    tmp_path: Path, auto_scroll: bool, at_end: bool, scrolls: bool
) -> None:
    (tmp_path / "stdout.log").write_text("new\n")
    output = StreamLog("stdout")
    output.auto_scroll = auto_scroll
    with (
        mock.patch.object(
            StreamLog, "is_mounted", new_callable=mock.PropertyMock, return_value=True
        ),
        mock.patch.object(
            StreamLog,
            "is_vertical_scroll_end",
            new_callable=mock.PropertyMock,
            return_value=at_end,
        ),
        mock.patch.object(StreamLog, "scroll_end") as scroll,
    ):
        output.follow(tmp_path)
        output.follow(tmp_path)
    if scrolls:
        scroll.assert_called_once_with(animate=False, immediate=True, x_axis=False)
    else:
        scroll.assert_not_called()


def test_does_not_scroll_before_mounting(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("new\n")
    output = StreamLog("stdout")
    with mock.patch.object(StreamLog, "scroll_end") as scroll:
        output.follow(tmp_path)
    scroll.assert_not_called()


def test_reset_starts_over_for_another_folder(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("old\npartial")
    (tmp_path / "r2" / "stdout.log").write_text("hi\n")
    output = StreamLog("stdout")
    output.follow(tmp_path / "r1")
    output.first, output.window, output._width = 1, ["partial"], 7
    output._line_cache[0] = mock.Mock()
    output.reset()
    assert (output.segments, output.first, output.window) == ([], 0, [])
    assert (output._line_cache, output._width, output.virtual_size) == ({}, 0, (0, 0))
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


def test_loads_the_rows_around_the_one_asked_for(
    tmp_path: Path, sized: mock.Mock
) -> None:
    (tmp_path / "stdout.log").write_text("".join(f"{n}\n" for n in range(400)))
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.load(250)
    assert output.first == 150
    assert output.window == [str(n) for n in range(150, 355)]


def test_loads_from_the_top_near_the_start(tmp_path: Path, sized: mock.Mock) -> None:
    (tmp_path / "stdout.log").write_text("a\nb\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output._line_cache[0] = mock.Mock()
    output.load(1)
    assert (output.first, output.window, output._line_cache) == (0, ["a", "b"], {})


def test_loading_wider_rows_widens_the_scrollable_area(
    tmp_path: Path, sized: mock.Mock
) -> None:
    (tmp_path / "stdout.log").write_text(
        "\x1b[31mred\x1b[0m\n界\n\x1b[31mxx\rfirst\r\x1b[32mabcd\x1b[0m\n"
    )
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.load(0)
    assert output.virtual_size == (4, 3)


def test_loading_narrower_rows_keeps_the_width(
    tmp_path: Path, sized: mock.Mock
) -> None:
    (tmp_path / "stdout.log").write_text("ab\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output._width = 9
    with mock.patch.object(StreamLog, "widen") as widen:
        output.load(0)
    assert output._width == 9
    widen.assert_not_called()


def test_loading_nothing_keeps_the_width(sized: mock.Mock) -> None:
    output = StreamLog("stdout")
    output.load(0)
    assert (output.window, output._width) == ([], 0)


def test_keeps_ansi_raw_until_a_line_is_rendered(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("\x1b[31mred\x1b[0m plain\x1b[2K\n")
    output = StreamLog("stdout")
    with mock.patch("labnotes.tui.stream_log.Text.from_ansi") as parse:
        output.follow(tmp_path)
    parse.assert_not_called()
    assert shown(output) == ["\x1b[31mred\x1b[0m plain\x1b[2K"]


@pytest.fixture
def rendered_line() -> Iterator[mock.Mock]:
    line_text = mock.Mock(plain="red")
    line_text.__len__ = mock.Mock(return_value=3)
    line_text.render.return_value = []
    with (
        mock.patch("labnotes.tui.stream_log.Text.from_ansi", return_value=line_text),
        mock.patch("labnotes.tui.stream_log.Strip"),
    ):
        yield line_text


def rendering(
    scroll: tuple[int, int] = (0, 0), selection: object = None
) -> mock._patch:  # type: ignore[type-arg]
    return mock.patch.multiple(
        StreamLog,
        scroll_offset=mock.PropertyMock(return_value=scroll),
        size=mock.PropertyMock(return_value=mock.Mock(width=10, height=5)),
        rich_style=mock.PropertyMock(),
        text_selection=mock.PropertyMock(return_value=selection),
        app=mock.PropertyMock(),
        screen=mock.PropertyMock(),
    )


def test_renders_a_blank_row_past_the_end(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    with (
        rendering(),
        mock.patch("labnotes.tui.stream_log.Strip") as strip,
        mock.patch.object(StreamLog, "load") as load,
    ):
        assert output.render_line(0) is strip.blank.return_value
    load.assert_not_called()


def test_reuses_a_cached_visible_line(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("kept\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.window = ["kept"]
    cached = mock.Mock()
    cached.crop_extend.return_value.apply_offsets.return_value = cached
    output._line_cache[0] = cached
    with rendering():
        assert output.render_line(0) is cached


def test_loads_a_row_outside_the_window_before_rendering(
    tmp_path: Path, rendered_line: mock.Mock
) -> None:
    (tmp_path / "stdout.log").write_text("".join(f"{n}\n" for n in range(500)))
    output = StreamLog("stdout")
    output.follow(tmp_path)
    with rendering(scroll=(0, 400)), mock.patch.object(StreamLog, "call_after_refresh"):
        output.render_line(2)
    assert (output.first, len(output.window)) == (302, 198)


@pytest.mark.parametrize(
    ("first", "loads"), [(1, False), (4, False), (0, True), (5, True)]
)
def test_a_row_inside_the_window_renders_without_loading(
    tmp_path: Path, rendered_line: mock.Mock, first: int, loads: bool
) -> None:
    (tmp_path / "stdout.log").write_text("".join(f"{n}\n" for n in range(10)))
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.first, output.window = first, ["a", "b", "c", "d"]
    with rendering(scroll=(0, 2)), mock.patch.object(StreamLog, "load") as load:
        load.side_effect = lambda row: setattr(output, "first", row)
        output.render_line(2)
    assert load.called is loads


@pytest.mark.parametrize("span", [None, (0, -1), (1, 2)])
def test_selection_is_applied_to_a_visible_line(
    tmp_path: Path, span: tuple[int, int] | None, rendered_line: mock.Mock
) -> None:
    (tmp_path / "stdout.log").write_text("red\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.window = ["red"]
    selection = mock.Mock()
    selection.get_span.return_value = span
    with rendering(selection=selection):
        output.render_line(0)
        screen: Any = output.screen
    selection.get_span.assert_called_once_with(0)
    if span is None:
        rendered_line.stylize.assert_not_called()
    else:
        rendered_line.stylize.assert_called_once_with(
            screen.get_component_rich_style.return_value,
            span[0],
            3 if span[1] == -1 else span[1],
        )
    assert 0 not in output._line_cache


def test_renders_the_scrolled_row_cropped_to_the_visible_columns(
    tmp_path: Path, rendered_line: mock.Mock
) -> None:
    (tmp_path / "stdout.log").write_text("zero\none\ntwo\nthree\nfour\n")
    output = StreamLog("stdout")
    output.follow(tmp_path)
    output.window = ["zero", "one", "two", "three", "four"]
    with rendering(scroll=(2, 3)):
        style = output.rich_style
        rendered = output.render_line(1)
    assert list(output._line_cache) == [4]
    cropped: mock.Mock = output._line_cache[4].crop_extend  # type: ignore[assignment]
    cropped.assert_called_once_with(2, 12, style)
    cropped.return_value.apply_offsets.assert_called_once_with(2, 4)
    assert rendered is cropped.return_value.apply_offsets.return_value
