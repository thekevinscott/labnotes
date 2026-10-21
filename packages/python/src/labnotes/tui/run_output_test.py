from collections import deque
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.run_output import RunOutput

DROP_LAST_LINE = RunOutput.drop_last_line


@pytest.fixture(autouse=True)
def log() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch.object(RunOutput, "write") as write,
        mock.patch.object(RunOutput, "clear") as clear,
        mock.patch.object(RunOutput, "drop_last_line") as drop,
    ):
        yield {"write": write, "clear": clear, "drop": drop}


def written(log: dict[str, mock.MagicMock]) -> list[str]:
    return [call.args[0].plain for call in log["write"].call_args_list]


def append(path: Path, text: str) -> None:
    with path.open("a") as file:
        file.write(text)


def test_starts_empty(log: dict[str, mock.MagicMock]) -> None:
    output = RunOutput(id="output")
    assert output.id == "output"
    assert output.offsets == {"stdout": 0, "stderr": 0}
    assert (output.last_stream, output.mid_line) == (None, False)
    log["clear"].assert_called_once_with()


def test_follows_nothing_before_a_run_writes_output(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    output.follow(tmp_path)
    assert written(log) == []
    assert output.offsets == {"stdout": 0, "stderr": 0}


@pytest.mark.parametrize("stdout", [None, ""])
def test_follows_stderr_without_stdout(
    tmp_path: Path, log: dict[str, mock.MagicMock], stdout: str | None
) -> None:
    if stdout is not None:
        (tmp_path / "stdout.log").write_text(stdout)
    (tmp_path / "stderr.log").write_text("oops\n")
    output = RunOutput()
    output.follow(tmp_path)
    assert written(log) == ["oops"]
    assert output.offsets == {"stdout": 0, "stderr": 5}


def test_appends_only_new_bytes_on_each_follow(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    output.follow(tmp_path)
    append(tmp_path / "stdout.log", "two\nthree\n")
    output.follow(tmp_path)
    assert written(log) == ["one", "two\nthree"]
    assert output.offsets == {"stdout": 14, "stderr": 0}


def test_decodes_characters_split_across_follows(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_bytes(b"caf\xc3")
    output.follow(tmp_path)
    with (tmp_path / "stdout.log").open("ab") as file:
        file.write(b"\xa9 done\n")
    output.follow(tmp_path)
    assert written(log) == ["caf", "café done"]
    assert output.offsets == {"stdout": 11, "stderr": 0}


def test_redraws_a_streams_own_unfinished_line(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_text("par")
    output.follow(tmp_path)
    assert output.mid_line
    log["drop"].assert_not_called()
    append(tmp_path / "stdout.log", "tial\nne")
    output.follow(tmp_path)
    log["drop"].assert_called_once_with()
    assert written(log) == ["par", "partial", "ne"]
    append(tmp_path / "stdout.log", "xt\n")
    output.follow(tmp_path)
    assert log["drop"].call_count == 2
    assert written(log) == ["par", "partial", "ne", "next"]
    assert not output.mid_line


def test_breaks_an_unfinished_line_before_the_other_stream(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
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
    log["drop"].assert_not_called()
    assert written(log) == ["next", "oops", "more", "warn", "end"]


def test_parses_ansi_into_styles(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    (tmp_path / "stdout.log").write_text("\x1b[31mred\x1b[0m plain\x1b[2K\n")
    output = RunOutput()
    output.follow(tmp_path)
    text = log["write"].call_args.args[0]
    assert text.plain == "red plain"
    assert [(span.start, span.end, str(span.style)) for span in text.spans] == [
        (0, 3, "color(1)")
    ]


def test_reset_starts_over_for_another_folder(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_bytes(b"cut \xe2\x82")
    (tmp_path / "r2" / "stdout.log").write_bytes(b"hi\n")
    (tmp_path / "r2" / "stderr.log").write_bytes(b"warn\n")
    output = RunOutput()
    output.follow(tmp_path / "r1")
    log["clear"].reset_mock()
    output.reset()
    log["clear"].assert_called_once_with()
    assert output.offsets == {"stdout": 0, "stderr": 0}
    assert (output.last_stream, output.mid_line) == (None, False)
    output.follow(tmp_path / "r2")
    assert written(log) == ["cut ", "hi", "warn"]


def test_reset_forgets_an_unfinished_line(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("partial")
    (tmp_path / "r2" / "stdout.log").write_text("more\n")
    output = RunOutput()
    output.follow(tmp_path / "r1")
    output.reset()
    output.follow(tmp_path / "r2")
    log["drop"].assert_not_called()
    assert written(log) == ["partial", "more"]


def test_drops_a_deferred_write_before_the_size_is_known() -> None:
    output = RunOutput()
    output._size_known = False
    output._deferred_renders = deque(["kept", "dropped"])  # type: ignore[list-item]
    DROP_LAST_LINE(output)
    assert list(output._deferred_renders) == ["kept"]


def test_drops_the_last_rendered_line() -> None:
    output = RunOutput()
    output._size_known = True
    output.lines = ["kept", "dropped"]  # type: ignore[list-item]
    output._line_cache = mock.Mock()
    with (
        mock.patch.object(RunOutput, "virtual_size", mock.Mock(width=9)),
        mock.patch("labnotes.tui.run_output.Size") as size,
        mock.patch.object(output, "refresh") as refresh,
    ):
        DROP_LAST_LINE(output)
        assert output.virtual_size is size.return_value
    size.assert_called_once_with(9, 1)
    assert output.lines == ["kept"]
    output._line_cache.clear.assert_called_once_with()
    refresh.assert_called_once_with()
