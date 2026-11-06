from collections.abc import Iterator
from contextlib import contextmanager
from io import BufferedReader
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.line_index import LineIndex


@pytest.fixture
def small(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("labnotes.line_index.BLOCK", 8)
    monkeypatch.setattr("labnotes.line_index.MAX_LINE", 6)


def rows(data: bytes) -> list[bytes]:
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return [line[:6] for line in lines]


def indexed(path: Path, data: bytes) -> LineIndex:
    path.write_bytes(data)
    index = LineIndex(path)
    index.extend()
    return index


def test_starts_with_nothing_indexed(tmp_path: Path) -> None:
    index = LineIndex(tmp_path / "out.log")
    assert (index.path, index.breaks, index.scanned) == (tmp_path / "out.log", [0], 0)
    assert (index.lines, index.rows, index.tail_start) == (0, 0, 0)


@pytest.mark.parametrize(
    ("data", "lines", "rows"),
    [(b"", 0, 0), (b"one", 0, 1), (b"one\n", 1, 1), (b"one\ntwo", 1, 2)],
)
def test_counts_complete_lines_and_an_unfinished_row(
    tmp_path: Path, data: bytes, lines: int, rows: int
) -> None:
    index = indexed(tmp_path / "out.log", data)
    assert (index.lines, index.rows, index.scanned) == (lines, rows, len(data))


@pytest.mark.usefixtures("small")
def test_records_newlines_before_each_block(tmp_path: Path) -> None:
    index = indexed(tmp_path / "out.log", b"a\nb\nc\nd\nee\nffff\ngggggggg\n")
    assert index.breaks == [0, 4, 6, 6]
    assert index.tail_start == 25


def test_extends_from_where_it_stopped(tmp_path: Path) -> None:
    path = tmp_path / "out.log"
    index = indexed(path, b"one\ntw")
    assert not index.extend()
    with path.open("ab") as file:
        file.write(b"o\nthree\n")
    assert index.extend()
    assert (index.lines, index.rows) == (3, 3)
    assert index.read(0, 5) == [b"one", b"two", b"three"]


def logs() -> list[bytes]:
    lengths = [0, 1, 5, 6, 7, 9, 20]
    return [
        b"\n".join(b"x" * lengths[line * step % 7] for line in range(lines)) + ending
        for lines in range(13)
        for step in range(1, 8)
        for ending in [b"", b"\n", b"tail"]
    ]


@pytest.mark.usefixtures("small")
def test_reads_any_window_of_a_log(tmp_path: Path) -> None:
    for data in logs():
        index = indexed(tmp_path / "out.log", data)
        expected = rows(data)
        assert index.rows == len(expected)
        for first in range(len(expected) + 2):
            for count in range(4):
                assert index.read(first, count) == expected[first : first + count]


@pytest.mark.usefixtures("small")
def test_cuts_a_long_line_and_resumes_at_the_next(tmp_path: Path) -> None:
    index = indexed(tmp_path / "out.log", b"short\n" + b"y" * 30 + b"\nafter\n")
    assert index.read(0, 3) == [b"short", b"yyyyyy", b"after"]


class Counting:
    def __init__(self, file: BufferedReader, read: list[int]) -> None:
        self.file = file
        self.counted = read

    def __enter__(self) -> "Counting":
        return self

    def __exit__(self, *_: object) -> None:
        self.file.close()

    def seek(self, offset: int) -> int:
        return self.file.seek(offset)

    def read(self, size: int) -> bytes:
        data = self.file.read(size)
        self.counted.append(len(data))
        return data


@contextmanager
def counting() -> Iterator[list[int]]:
    read: list[int] = []
    original = Path.open

    def opened(path: Path, *args: Any, **kwargs: Any) -> Counting:
        return Counting(original(path, *args, **kwargs), read)

    with mock.patch.object(Path, "open", opened):
        yield read


def test_reading_a_window_does_not_scale_with_the_log(tmp_path: Path) -> None:
    sizes = []
    for lines in (1_000, 200_000):
        index = indexed(tmp_path / f"{lines}.log", b"a line of output\n" * lines)
        with counting() as counted:
            assert index.read(lines - 250, 250) == [b"a line of output"] * 250
        sizes.append(sum(counted))
    assert sizes[1] <= 3 * 64 * 1024
    assert sizes[1] <= sizes[0] + 2 * 64 * 1024


def test_the_index_stays_small_for_a_large_log(tmp_path: Path) -> None:
    index = indexed(tmp_path / "out.log", b"x\n" * 2_000_000)
    assert len(index.breaks) == 4_000_000 // (64 * 1024) + 1
