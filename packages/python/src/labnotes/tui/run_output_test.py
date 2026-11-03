from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.run_output import RunOutput


def append(path: Path, text: str) -> None:
    with path.open("a") as file:
        file.write(text)


def test_starts_empty() -> None:
    output = RunOutput(id="output")
    assert output.id == "output"
    assert output.offsets == {"stdout": 0, "stderr": 0}
    assert (output.last_stream, output.mid_line) == (None, False)
    assert list(output.lines) == []
    assert output.auto_scroll


def test_empty_write_leaves_the_log_unchanged() -> None:
    output = RunOutput()
    assert output.write_lines([]) is output
    assert list(output.lines) == []


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
    output = RunOutput()
    output.auto_scroll = auto_scroll
    with (
        mock.patch.object(
            RunOutput, "is_mounted", new_callable=mock.PropertyMock, return_value=True
        ),
        mock.patch.object(
            RunOutput,
            "is_vertical_scroll_end",
            new_callable=mock.PropertyMock,
            return_value=True,
        ),
        mock.patch.object(RunOutput, "scroll_end") as scroll,
    ):
        output.write_lines(["new"], scroll_end=scroll_end)
    if scrolls:
        scroll.assert_called_once_with(animate=False, immediate=True, x_axis=False)
    else:
        scroll.assert_not_called()


def test_follows_nothing_before_a_run_writes_output(tmp_path: Path) -> None:
    output = RunOutput()
    output.follow(tmp_path)
    assert list(output.lines) == []
    assert output.offsets == {"stdout": 0, "stderr": 0}


@pytest.mark.parametrize("stdout", [None, ""])
def test_follows_stderr_without_stdout(tmp_path: Path, stdout: str | None) -> None:
    if stdout is not None:
        (tmp_path / "stdout.log").write_text(stdout)
    (tmp_path / "stderr.log").write_text("oops\n")
    output = RunOutput()
    output.follow(tmp_path)
    assert list(output.lines) == ["oops"]
    assert output.offsets == {"stdout": 0, "stderr": 5}


def test_appends_only_new_bytes_on_each_follow(tmp_path: Path) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    output.follow(tmp_path)
    append(tmp_path / "stdout.log", "two\nthree\n")
    output.follow(tmp_path)
    assert list(output.lines) == ["one", "two", "three"]
    assert output.offsets == {"stdout": 14, "stderr": 0}


def test_decodes_characters_split_across_follows(tmp_path: Path) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_bytes(b"caf\xc3")
    output.follow(tmp_path)
    with (tmp_path / "stdout.log").open("ab") as file:
        file.write(b"\xa9 done\n")
    output.follow(tmp_path)
    assert list(output.lines) == ["café done"]
    assert output.offsets == {"stdout": 11, "stderr": 0}


def test_redraws_a_streams_own_unfinished_line(tmp_path: Path) -> None:
    output = RunOutput()
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


def test_breaks_an_unfinished_line_before_the_other_stream(tmp_path: Path) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_text("next")
    (tmp_path / "stderr.log").write_text("oops\n")
    output.follow(tmp_path)
    assert (output.last_stream, output.mid_line) == ("stderr", False)
    append(tmp_path / "stdout.log", "more\n")
    output.follow(tmp_path)
    append(tmp_path / "stderr.log", "warn")
    output.follow(tmp_path)
    assert (output.last_stream, output.mid_line) == ("stderr", True)
    append(tmp_path / "stdout.log", "end\n")
    output.follow(tmp_path)
    assert list(output.lines) == ["next", "oops", "more", "warn", "end"]


def test_keeps_ansi_raw_until_a_line_is_rendered(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("\x1b[31mred\x1b[0m plain\x1b[2K\n")
    output = RunOutput()
    with mock.patch("labnotes.tui.run_output.Text.from_ansi") as parse:
        output.follow(tmp_path)
    parse.assert_not_called()
    assert list(output.lines) == ["\x1b[31mred\x1b[0m plain\x1b[2K"]


def test_reset_starts_over_for_another_folder(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_bytes(b"cut \xe2\x82")
    (tmp_path / "r2" / "stdout.log").write_bytes(b"hi\n")
    (tmp_path / "r2" / "stderr.log").write_bytes(b"warn\n")
    output = RunOutput()
    output.follow(tmp_path / "r1")
    output.reset()
    assert output.offsets == {"stdout": 0, "stderr": 0}
    assert (output.last_stream, output.mid_line) == (None, False)
    assert list(output.lines) == []
    output.follow(tmp_path / "r2")
    assert list(output.lines) == ["hi", "warn"]


def test_reset_forgets_an_unfinished_line(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("partial")
    (tmp_path / "r2" / "stdout.log").write_text("more\n")
    output = RunOutput()
    output.follow(tmp_path / "r1")
    output.reset()
    output.follow(tmp_path / "r2")
    assert list(output.lines) == ["more"]


def test_dropping_an_unfinished_line_invalidates_its_cache() -> None:
    output = RunOutput()
    output.write_lines(["kept", "partial"])
    output._render_line_cache[1] = mock.Mock()
    output.drop_unfinished()
    assert list(output.lines) == ["kept"]
    assert 1 not in output._render_line_cache
    assert output.virtual_size.height == 1


def test_reuses_a_cached_visible_line() -> None:
    output = RunOutput()
    output.write_lines(["kept"])
    cached = mock.Mock()
    output._render_line_cache[0] = cached
    with mock.patch.object(
        RunOutput, "text_selection", new_callable=mock.PropertyMock
    ) as selected:
        selected.return_value = None
        assert output._render_line_strip(0, mock.Mock()) is cached


@pytest.mark.parametrize("span", [None, (0, -1), (1, 2)])
def test_selection_is_applied_to_a_visible_line(span: tuple[int, int] | None) -> None:
    output = RunOutput()
    output.write_lines(["red"])
    selection = mock.Mock()
    selection.get_span.return_value = span
    line_text = mock.Mock(plain="red")
    line_text.__len__ = mock.Mock(return_value=3)
    line_text.render.return_value = []
    with (
        mock.patch.object(
            RunOutput, "text_selection", new_callable=mock.PropertyMock
        ) as selected,
        mock.patch.object(
            RunOutput, "screen", new_callable=mock.PropertyMock
        ) as screen,
        mock.patch.object(RunOutput, "app", new_callable=mock.PropertyMock),
        mock.patch("labnotes.tui.run_output.Text.from_ansi", return_value=line_text),
    ):
        selected.return_value = selection
        output._render_line_strip(0, mock.Mock())
    selection.get_span.assert_called_once_with(0)
    if span is None:
        line_text.stylize.assert_not_called()
    else:
        line_text.stylize.assert_called_once_with(
            screen.return_value.get_component_rich_style.return_value,
            span[0],
            3 if span[1] == -1 else span[1],
        )
    assert 0 not in output._render_line_cache


def test_moves_to_the_newest_invocation_log_from_its_start(tmp_path: Path) -> None:
    output = RunOutput()
    (tmp_path / "stdout-20261102-090000-000000.txt").write_text("first\n")
    output.follow(tmp_path)
    (tmp_path / "stdout-20261102-100000-000000.txt").write_text("next\n")
    output.follow(tmp_path)
    output.follow(tmp_path)
    assert list(output.lines) == ["first", "next"]
    assert output.offsets == {"stdout": 5, "stderr": 0}


def test_switches_to_a_log_path_that_sorts_before_the_previous_one(
    tmp_path: Path,
) -> None:
    older_name = tmp_path / "z.log"
    newer_name = tmp_path / "a.log"
    older_name.write_text("first line\n")
    newer_name.write_text("new\n")
    output = RunOutput()
    with mock.patch(
        "labnotes.tui.run_output.latest_log",
        side_effect=[
            older_name,
            tmp_path / "stderr.log",
            newer_name,
            tmp_path / "stderr.log",
        ],
    ):
        output.follow(tmp_path)
        output.follow(tmp_path)
    assert list(output.lines) == ["first line", "new"]
    assert output.offsets["stdout"] == 4
