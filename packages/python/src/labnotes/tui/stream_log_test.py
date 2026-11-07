import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.stream_log import StreamLog


def append(path: Path, text: str) -> None:
    with path.open("a") as file:
        file.write(text)


def test_starts_empty() -> None:
    output = StreamLog("stdout", id="output")
    assert (output.id, output.stream, output.path) == ("output", "stdout", None)
    assert output.read_to == 0
    assert not output.mid_line
    assert list(output.lines) == []
    assert output.auto_scroll


def test_empty_write_leaves_the_log_unchanged() -> None:
    output = StreamLog("stdout")
    assert output.write_lines([]) is output
    assert list(output.lines) == []


def test_colored_lines_use_visible_cell_width_for_horizontal_scrolling() -> None:
    output = StreamLog("stdout")
    output.write_lines(["\x1b[31mred\x1b[0m", "界"])
    assert output.virtual_size.width == 3


def test_replacing_an_unfinished_line_updates_horizontal_scroll_width() -> None:
    output = StreamLog("stdout")
    output.write_lines(["\x1b[31mcolored\x1b[0m"])
    output.drop_unfinished()
    output.write_lines(["ok"])
    assert output.virtual_size.width == 2


@pytest.mark.parametrize(
    ("auto_scroll", "scroll_end", "scrolls"),
    [
        (True, None, True),
        (False, None, False),
        (True, False, False),
        (False, True, True),
    ],
)
def test_scrolls_to_the_newest_line_only_from_the_end(
    auto_scroll: bool, scroll_end: bool | None, scrolls: bool
) -> None:
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
            return_value=True,
        ),
        mock.patch.object(StreamLog, "scroll_end") as scroll,
    ):
        output.write_lines(["new"], scroll_end=scroll_end)
    if scrolls:
        scroll.assert_called_once_with(animate=False, immediate=True, x_axis=False)
    else:
        scroll.assert_not_called()


def test_follows_nothing_before_a_run_writes_output(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    output.follow(tmp_path)
    assert list(output.lines) == []
    assert output.read_to == 0


def test_follows_its_own_stream_only(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("out\n")
    (tmp_path / "stderr.log").write_text("oops\n")
    output = StreamLog("stderr")
    output.follow(tmp_path)
    assert list(output.lines) == ["oops"]
    assert (output.read_to, output.path) == (5, tmp_path / "stderr.log")


def test_appends_only_new_bytes_on_each_follow(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    output.follow(tmp_path)
    append(tmp_path / "stdout.log", "two\nthree\n")
    output.follow(tmp_path)
    assert list(output.lines) == ["one", "two", "three"]
    assert output.read_to == 14


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
    assert list(output.lines) == ["café done"]
    assert output.read_to == 11


def test_redraws_a_streams_own_unfinished_line(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout.log").write_text("par")
    output.follow(tmp_path)
    assert list(output.lines) == ["par"]
    assert output.mid_line
    append(tmp_path / "stdout.log", "tial\nne")
    output.follow(tmp_path)
    assert list(output.lines) == ["partial", "ne"]
    append(tmp_path / "stdout.log", "xt\n")
    output.follow(tmp_path)
    assert list(output.lines) == ["partial", "next"]
    assert not output.mid_line


@pytest.mark.parametrize(
    ("text", "count"),
    [("", 0), ("one", 0), ("one\n", 1), ("one\ntwo", 1), ("one\ntwo\nthree", 2)],
)
def test_counts_only_complete_lines(tmp_path: Path, text: str, count: int) -> None:
    (tmp_path / "stdout.log").write_text(text)
    output = StreamLog("stdout")
    output.follow(tmp_path)
    assert output.count == count


def test_keeps_ansi_raw_until_a_line_is_rendered(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("\x1b[31mred\x1b[0m plain\x1b[2K\n")
    output = StreamLog("stdout")
    with mock.patch("labnotes.tui.stream_log.Text.from_ansi") as parse:
        output.follow(tmp_path)
    parse.assert_not_called()
    assert list(output.lines) == ["\x1b[31mred\x1b[0m plain\x1b[2K"]


def test_reset_starts_over_for_another_folder(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_bytes(b"cut \xe2\x82")
    (tmp_path / "r2" / "stdout.log").write_bytes(b"hi\n")
    (tmp_path / "r2" / "stderr.log").write_bytes(b"warn\n")
    output = StreamLog("stdout")
    output.follow(tmp_path / "r1")
    output.reset()
    assert output.read_to == 0
    assert not output.mid_line
    assert list(output.lines) == []
    output.follow(tmp_path / "r2")
    assert list(output.lines) == ["hi"]


def test_reset_forgets_an_unfinished_line(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("partial")
    (tmp_path / "r2" / "stdout.log").write_text("more\n")
    output = StreamLog("stdout")
    output.follow(tmp_path / "r1")
    output.reset()
    output.follow(tmp_path / "r2")
    assert list(output.lines) == ["more"]


def test_dropping_an_unfinished_line_invalidates_its_cache() -> None:
    output = StreamLog("stdout")
    output.write_lines(["kept", "partial"])
    output._line_cache[1] = mock.Mock()
    output.drop_unfinished()
    assert list(output.lines) == ["kept"]
    assert 1 not in output._line_cache
    assert output.virtual_size.height == 1


def test_reuses_a_cached_visible_line() -> None:
    output = StreamLog("stdout")
    output.write_lines(["kept"])
    cached = mock.Mock()
    cached.crop_extend.return_value.apply_offsets.return_value = cached
    output._line_cache[0] = cached
    with mock.patch.object(
        StreamLog, "text_selection", new_callable=mock.PropertyMock
    ) as selected:
        selected.return_value = None
        assert output.render_line(0) is cached


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


@pytest.mark.parametrize("span", [None, (0, -1), (1, 2)])
def test_selection_is_applied_to_a_visible_line(
    span: tuple[int, int] | None, rendered_line: mock.Mock
) -> None:
    output = StreamLog("stdout")
    output.write_lines(["red"])
    selection = mock.Mock()
    selection.get_span.return_value = span
    with (
        mock.patch.object(
            StreamLog, "text_selection", new_callable=mock.PropertyMock
        ) as selected,
        mock.patch.object(
            StreamLog, "screen", new_callable=mock.PropertyMock
        ) as screen,
        mock.patch.object(StreamLog, "app", new_callable=mock.PropertyMock),
    ):
        selected.return_value = selection
        output.render_line(0)
    selection.get_span.assert_called_once_with(0)
    if span is None:
        rendered_line.stylize.assert_not_called()
    else:
        rendered_line.stylize.assert_called_once_with(
            screen.return_value.get_component_rich_style.return_value,
            span[0],
            3 if span[1] == -1 else span[1],
        )
    assert 0 not in output._line_cache


def test_moves_to_the_newest_invocation_log_from_its_start(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout-20261102-090000-000000.txt").write_text("first\n")
    (tmp_path / "run.json").write_text(
        json.dumps({"invocations": [{"stdout": "stdout-20261102-090000-000000.txt"}]})
    )
    output.follow(tmp_path)
    (tmp_path / "stdout-20261102-100000-000000.txt").write_text("next\n")
    (tmp_path / "run.json").write_text(
        json.dumps({"invocations": [{"stdout": "stdout-20261102-100000-000000.txt"}]})
    )
    output.follow(tmp_path)
    output.follow(tmp_path)
    assert list(output.lines) == ["first", "next"]
    assert output.read_to == 5


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
    assert list(output.lines) == ["first line", "new"]
    assert output.read_to == 4


def test_clearing_forgets_the_scrollable_size() -> None:
    output = StreamLog("stdout")
    output.write_lines(["wide line", "x"])
    output.clear()
    assert (output._width, output.virtual_size) == (0, (0, 0))


def test_width_counts_only_text_after_the_last_carriage_return() -> None:
    output = StreamLog("stdout")
    output.write_lines(["\x1b[31mxx\rfirst\r\x1b[32mabcd\x1b[0m"])
    assert output.virtual_size == (4, 1)


@pytest.mark.parametrize(
    ("lines", "width"), [(["wide", "ab"], 4), (["ab", "wide"], 2), (["only"], 0)]
)
def test_dropping_an_unfinished_line_keeps_the_remaining_width(
    lines: list[str], width: int
) -> None:
    output = StreamLog("stdout")
    output.write_lines(lines)
    output.drop_unfinished()
    assert (output._width, output.virtual_size) == (width, (width, len(lines) - 1))


def test_renders_the_scrolled_row_cropped_to_the_visible_columns(
    rendered_line: mock.Mock,
) -> None:
    output = StreamLog("stdout")
    output.write_lines(["zero", "one", "two", "three", "four"])
    style = mock.Mock()
    with (
        mock.patch.object(
            StreamLog,
            "scroll_offset",
            new_callable=mock.PropertyMock,
            return_value=(2, 3),
        ),
        mock.patch.object(
            StreamLog,
            "size",
            new_callable=mock.PropertyMock,
            return_value=mock.Mock(width=10),
        ),
        mock.patch.object(
            StreamLog, "rich_style", new_callable=mock.PropertyMock, return_value=style
        ),
        mock.patch.object(
            StreamLog,
            "text_selection",
            new_callable=mock.PropertyMock,
            return_value=None,
        ),
        mock.patch.object(StreamLog, "app", new_callable=mock.PropertyMock),
    ):
        rendered = output.render_line(1)
    assert list(output._line_cache) == [4]
    cropped: mock.Mock = output._line_cache[4].crop_extend  # type: ignore[assignment]
    cropped.assert_called_once_with(2, 12, style)
    cropped.return_value.apply_offsets.assert_called_once_with(2, 4)
    assert rendered is cropped.return_value.apply_offsets.return_value


def test_rereads_a_log_that_was_truncated(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    log = tmp_path / "stdout.log"
    log.write_text("first line\nsecond\n")
    output.follow(tmp_path)
    assert output.lines == ["first line", "second"]

    log.write_text("new\n")
    output.follow(tmp_path)

    assert output.lines == ["new"]
    assert output.read_to == 4


def test_rereads_a_log_that_was_deleted_and_recreated(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    log = tmp_path / "stdout.log"
    log.write_text("first line\nsecond\n")
    output.follow(tmp_path)

    log.unlink()
    output.follow(tmp_path)
    assert output.lines == []

    log.write_text("again\n")
    output.follow(tmp_path)
    assert output.lines == ["again"]


def test_a_missing_log_does_not_reset_the_view(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    output.follow(tmp_path)
    assert output.lines == ["one"]


def test_a_deleted_log_clears_the_view(tmp_path: Path) -> None:
    output = StreamLog("stdout")
    log = tmp_path / "stdout.log"
    log.write_text("a")
    output.follow(tmp_path)
    assert output.read_to == 1

    log.unlink()
    output.follow(tmp_path)

    assert output.lines == []
    assert output.read_to == 0
