import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.ordered_output import OrderedOutput


@pytest.fixture
def files(tmp_path: Path) -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.ordered_output.output_files",
        return_value={
            "output": tmp_path / "output.jsonl",
            "stdout": tmp_path / "stdout.log",
            "stderr": tmp_path / "stderr.log",
        },
    ) as files:
        yield files


@pytest.fixture
def latest_log() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.ordered_output.latest_log",
        side_effect=lambda folder, stream: folder / f"{stream}.log",
    ) as latest_log:
        yield latest_log


def append(path: Path, data: bytes) -> None:
    with path.open("ab") as file:
        file.write(data)


def write(folder: Path, stream: str, data: bytes, index: str = "output.jsonl") -> None:
    log = folder / ("stdout.log" if stream == "stdout" else "stderr.log")
    append(log, data)
    entry = {"stream": stream, "end": log.stat().st_size, "time": 1.0}
    append(folder / index, json.dumps(entry).encode() + b"\n")


def test_reads_nothing_before_the_index_exists(
    tmp_path: Path, files: mock.MagicMock
) -> None:
    assert OrderedOutput().read(tmp_path) == []
    files.assert_called_once_with(tmp_path)


def test_replays_both_streams_in_write_order(
    tmp_path: Path, files: mock.MagicMock
) -> None:
    write(tmp_path, "stdout", b"out 0\n")
    write(tmp_path, "stderr", b"err 0\n")
    write(tmp_path, "stdout", b"out 1\n")
    write(tmp_path, "stderr", b"err 1\n")

    assert OrderedOutput().read(tmp_path) == [
        ("stdout", b"out 0\n"),
        ("stderr", b"err 0\n"),
        ("stdout", b"out 1\n"),
        ("stderr", b"err 1\n"),
    ]


def test_reads_one_streams_consecutive_entries_at_once(
    tmp_path: Path, files: mock.MagicMock
) -> None:
    write(tmp_path, "stdout", b"a")
    write(tmp_path, "stdout", b"b")
    write(tmp_path, "stderr", b"c")

    assert OrderedOutput().read(tmp_path) == [("stdout", b"ab"), ("stderr", b"c")]


def test_reads_only_new_entries_on_each_read(
    tmp_path: Path, files: mock.MagicMock
) -> None:
    output = OrderedOutput()
    write(tmp_path, "stdout", b"first\n")
    assert output.read(tmp_path) == [("stdout", b"first\n")]

    write(tmp_path, "stderr", b"second\n")
    write(tmp_path, "stdout", b"third\n")

    assert output.read(tmp_path) == [("stderr", b"second\n"), ("stdout", b"third\n")]
    assert output.read(tmp_path) == []
    assert output.offsets == {"stdout": 12, "stderr": 7}


def test_leaves_log_bytes_the_index_does_not_cover_yet(
    tmp_path: Path, files: mock.MagicMock
) -> None:
    output = OrderedOutput()
    write(tmp_path, "stdout", b"indexed")
    append(tmp_path / "stdout.log", b" pending")

    assert output.read(tmp_path) == [("stdout", b"indexed")]

    append(tmp_path / "output.jsonl", b'{"stream": "stdout", "end": 15}\n')

    assert output.read(tmp_path) == [("stdout", b" pending")]


def test_holds_an_index_line_until_it_ends(
    tmp_path: Path, files: mock.MagicMock
) -> None:
    output = OrderedOutput()
    append(tmp_path / "stdout.log", b"abc")
    append(tmp_path / "output.jsonl", b'{"stream": "stdout", "end": 3')

    assert output.read(tmp_path) == []

    append(tmp_path / "output.jsonl", b"}\n")

    assert output.read(tmp_path) == [("stdout", b"abc")]


@pytest.mark.parametrize(
    "line",
    [
        b"not json",
        b"\xff",
        b"[1]",
        b"3",
        b'{"stream": "stdout"}',
        b'{"stream": "other", "end": 1}',
        b'{"stream": "stdout", "end": "1"}',
        b'{"stream": "stdout", "end": 0}',
    ],
)
def test_skips_an_index_line_it_cannot_use(
    tmp_path: Path, files: mock.MagicMock, line: bytes
) -> None:
    append(tmp_path / "stdout.log", b"abc")
    append(tmp_path / "output.jsonl", line + b"\n")
    write(tmp_path, "stderr", b"err")

    assert OrderedOutput().read(tmp_path) == [("stderr", b"err")]


def test_starts_over_at_a_new_invocations_index(
    tmp_path: Path, files: mock.MagicMock
) -> None:
    output = OrderedOutput()
    write(tmp_path, "stdout", b"old\n")
    assert output.read(tmp_path) == [("stdout", b"old\n")]

    files.return_value = {
        "output": tmp_path / "output-2.jsonl",
        "stdout": tmp_path / "stdout-2.txt",
        "stderr": tmp_path / "stderr-2.txt",
    }
    append(tmp_path / "stdout-2.txt", b"new\n")
    append(tmp_path / "output-2.jsonl", b'{"stream": "stdout", "end": 4}\n')

    assert output.read(tmp_path) == [("stdout", b"new\n")]
    assert output.index_read == len(b'{"stream": "stdout", "end": 4}\n')


def test_reads_each_log_in_turn_for_a_run_without_an_index(
    tmp_path: Path, files: mock.MagicMock, latest_log: mock.MagicMock
) -> None:
    files.return_value = None
    append(tmp_path / "stdout.log", b"out 0\nout 1\n")
    append(tmp_path / "stderr.log", b"err 0\n")
    output = OrderedOutput()

    assert output.read(tmp_path) == [
        ("stdout", b"out 0\nout 1\n"),
        ("stderr", b"err 0\n"),
    ]
    append(tmp_path / "stderr.log", b"err 1\n")
    assert output.read(tmp_path, ["stderr"]) == [("stderr", b"err 1\n")]
    assert output.read(tmp_path) == [("stdout", b""), ("stderr", b"")]


def test_skips_a_log_that_does_not_exist_yet(
    tmp_path: Path, files: mock.MagicMock, latest_log: mock.MagicMock
) -> None:
    files.return_value = None
    append(tmp_path / "stderr.log", b"err\n")

    assert OrderedOutput().read(tmp_path) == [("stderr", b"err\n")]


def test_starts_a_new_log_from_its_beginning(
    tmp_path: Path, files: mock.MagicMock, latest_log: mock.MagicMock
) -> None:
    files.return_value = None
    output = OrderedOutput()
    append(tmp_path / "stdout.log", b"old\n")
    output.read(tmp_path, ["stdout"])

    latest_log.side_effect = lambda folder, stream: folder / f"{stream}-2.txt"
    append(tmp_path / "stdout-2.txt", b"new\n")

    assert output.read(tmp_path, ["stdout"]) == [("stdout", b"new\n")]
    assert output.paths == {"stdout": tmp_path / "stdout-2.txt"}
