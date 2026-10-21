from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.run_output import RunOutput


@pytest.fixture(autouse=True)
def log() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch.object(RunOutput, "write") as write,
        mock.patch.object(RunOutput, "clear") as clear,
    ):
        yield {"write": write, "clear": clear}


def written(log: dict[str, mock.MagicMock]) -> list[str]:
    return [call.args[0] for call in log["write"].call_args_list]


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
    assert written(log) == ["oops\n"]
    assert output.offsets == {"stdout": 0, "stderr": 5}


def test_appends_only_new_bytes_on_each_follow(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_text("one\n")
    output.follow(tmp_path)
    assert output.offsets == {"stdout": 4, "stderr": 0}
    output.follow(tmp_path)
    with (tmp_path / "stdout.log").open("a") as file:
        file.write("two\n")
    output.follow(tmp_path)
    assert written(log) == ["one\n", "two\n"]
    assert output.offsets == {"stdout": 8, "stderr": 0}


def test_decodes_characters_split_across_follows(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_bytes(b"caf\xc3")
    output.follow(tmp_path)
    with (tmp_path / "stdout.log").open("ab") as file:
        file.write(b"\xa9 done\n")
    output.follow(tmp_path)
    assert written(log) == ["caf", "é done\n"]
    assert output.offsets == {"stdout": 11, "stderr": 0}


def test_continues_a_streams_own_unfinished_line(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_text("par")
    output.follow(tmp_path)
    with (tmp_path / "stdout.log").open("a") as file:
        file.write("tial\n")
    output.follow(tmp_path)
    assert written(log) == ["par", "tial\n"]


def test_breaks_an_unfinished_line_before_the_other_stream(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    output = RunOutput()
    (tmp_path / "stdout.log").write_text("next")
    (tmp_path / "stderr.log").write_text("oops\n")
    output.follow(tmp_path)
    assert (output.last_stream, output.mid_line) == ("stderr", False)
    with (tmp_path / "stdout.log").open("a") as file:
        file.write("more\n")
    output.follow(tmp_path)
    with (tmp_path / "stderr.log").open("a") as file:
        file.write("warn")
    output.follow(tmp_path)
    assert (output.last_stream, output.mid_line) == ("stderr", True)
    with (tmp_path / "stdout.log").open("a") as file:
        file.write("end\n")
    output.follow(tmp_path)
    assert written(log) == ["next", "\noops\n", "more\n", "warn", "\nend\n"]


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
    assert written(log) == ["cut ", "hi\n", "warn\n"]


def test_reset_forgets_an_unfinished_line(
    tmp_path: Path, log: dict[str, mock.MagicMock]
) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("partial")
    (tmp_path / "r2" / "stderr.log").write_text("oops\n")
    output = RunOutput()
    output.follow(tmp_path / "r1")
    output.reset()
    output.follow(tmp_path / "r2")
    assert written(log) == ["partial", "oops\n"]
