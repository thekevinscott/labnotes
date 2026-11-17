from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.file_tail import (
    MAX_LINES,
    PROMPT,
    SNIFF_BYTES,
    TAIL_BYTES,
    FileTail,
    read,
)


@pytest.fixture
def screen() -> Iterator[list[str]]:
    shown: list[str] = []

    def write(self: FileTail, text: str, scroll_end: bool | None = None) -> FileTail:
        shown.append(text)
        return self

    def clear(self: FileTail) -> FileTail:
        shown.clear()
        return self

    with (
        mock.patch.object(FileTail, "write", write),
        mock.patch.object(FileTail, "clear", clear),
        mock.patch.object(
            FileTail,
            "is_vertical_scroll_end",
            new_callable=mock.PropertyMock,
            return_value=True,
        ),
    ):
        yield shown


def text(shown: list[str]) -> str:
    return "".join(shown)


def append(path: Path, data: bytes) -> None:
    with path.open("ab") as file:
        file.write(data)


def test_asks_for_a_file_until_one_is_picked(screen: list[str]) -> None:
    tail = FileTail(id="tail")
    assert (tail.id, tail.path) == ("tail", None)
    assert text(screen) == PROMPT
    tail.follow()
    assert text(screen) == PROMPT


def test_shows_a_picked_file(screen: list[str], tmp_path: Path) -> None:
    path = tmp_path / "progress.log"
    path.write_text("step 1\nstep 2\n")
    tail = FileTail()
    tail.open(path)
    assert text(screen) == "step 1\nstep 2\n"


def test_follows_only_the_new_bytes(screen: list[str], tmp_path: Path) -> None:
    path = tmp_path / "progress.log"
    path.write_text("step 1\n")
    tail = FileTail()
    tail.open(path)
    tail.follow()
    append(path, b"step 2\n")
    tail.follow()
    assert screen == ["step 1\n", "step 2\n"]


def test_joins_a_character_split_across_writes(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "progress.log"
    path.write_bytes(b"caf\xc3")
    tail = FileTail()
    tail.open(path)
    append(path, b"\xa9\n")
    tail.follow()
    assert text(screen) == "café\n"


def test_starts_a_large_file_at_a_line_near_its_end(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "big.log"
    line = b"x" * 99 + b"\n"
    path.write_bytes(line * (3 * TAIL_BYTES // len(line)) + b"last line\n")
    tail = FileTail()
    tail.open(path)
    shown = text(screen)
    assert shown.endswith("last line\n")
    assert shown.startswith("x" * 99 + "\n")
    assert len(shown) <= TAIL_BYTES


def test_jumps_to_the_end_when_a_file_grows_past_the_tail(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "big.log"
    path.write_text("first\n")
    tail = FileTail()
    tail.open(path)
    append(path, b"y" * TAIL_BYTES + b"\nnewest\n")
    tail.follow()
    shown = text(screen)
    assert "first" not in shown
    assert shown == "newest\n"
    append(path, b"more\n")
    tail.follow()
    assert text(screen) == "newest\nmore\n"


def test_starts_over_when_a_file_shrinks(screen: list[str], tmp_path: Path) -> None:
    path = tmp_path / "progress.log"
    path.write_text("old run of lines\n")
    tail = FileTail()
    tail.open(path)
    path.write_text("new\n")
    tail.follow()
    assert text(screen) == "new\n"


def test_names_a_binary_file_instead_of_showing_it(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "plot.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00" + bytes(range(256)))
    tail = FileTail()
    tail.open(path)
    assert text(screen) == "plot.png is binary (265 bytes), not shown."
    tail.follow()
    assert screen == ["plot.png is binary (265 bytes), not shown."]
    append(path, b"\x00" * 1000)
    tail.follow()
    assert text(screen) == "plot.png is binary (1.3 kB), not shown."


def test_waits_for_an_empty_file_to_get_bytes(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "later.bin"
    path.write_bytes(b"")
    tail = FileTail()
    tail.open(path)
    assert text(screen) == ""
    path.write_bytes(b"\x00\x01")
    tail.follow()
    assert text(screen) == "later.bin is binary (2 bytes), not shown."


def test_says_once_when_the_file_is_gone_and_picks_it_up_again(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "progress.log"
    path.write_text("one\n")
    tail = FileTail()
    tail.open(path)
    path.unlink()
    tail.follow()
    tail.follow()
    assert screen == ["progress.log is gone."]
    path.write_text("two\n")
    tail.follow()
    assert text(screen) == "two\n"


def test_keeps_following_the_end_only_when_scrolled_there(tmp_path: Path) -> None:
    path = tmp_path / "progress.log"
    path.write_text("one\n")
    with (
        mock.patch.object(FileTail, "write") as write,
        mock.patch.object(FileTail, "clear"),
        mock.patch.object(
            FileTail,
            "is_vertical_scroll_end",
            new_callable=mock.PropertyMock,
            return_value=False,
        ),
    ):
        tail = FileTail()
        tail.open(path)
    write.assert_called_with("one\n", scroll_end=False)


def test_reset_drops_the_file(screen: list[str], tmp_path: Path) -> None:
    path = tmp_path / "progress.log"
    path.write_text("one\n")
    tail = FileTail()
    tail.open(path)
    tail.reset()
    assert (tail.path, text(screen)) == (None, PROMPT)


def test_says_when_a_file_cannot_be_read_and_recovers(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "private.log"
    path.write_text("secret\n")
    tail = FileTail()
    denied = PermissionError(13, "Permission denied")
    with mock.patch("labnotes.tui.file_tail.read", side_effect=denied):
        tail.open(path)
        tail.follow()
    assert screen == ["private.log can't be read: Permission denied."]
    tail.follow()
    assert text(screen) == "secret\n"


def test_says_gone_when_a_file_vanishes_between_stat_and_read(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "brief.log"
    path.write_text("x\n")
    tail = FileTail()
    with mock.patch(
        "labnotes.tui.file_tail.read", side_effect=FileNotFoundError(2, "gone")
    ):
        tail.open(path)
    assert screen == ["brief.log is gone."]


def test_keeps_the_last_64_kib_and_10000_lines() -> None:
    assert (TAIL_BYTES, SNIFF_BYTES, MAX_LINES) == (65536, 8192, 10_000)


def test_reads_the_bytes_between_two_offsets(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"0123456789")
    assert read(path, 2, 5) == b"234"


def test_starts_exactly_one_line_into_the_last_64_kib(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "big.log"
    data = (b"x" * 99 + b"\n") * 1320 + b"last line\n"
    path.write_bytes(data)
    tail = FileTail()
    tail.open(path)
    end = data[-TAIL_BYTES:]
    assert text(screen) == end[end.find(b"\n") + 1 :].decode()


def test_appends_growth_of_exactly_the_tail_size(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "progress.log"
    path.write_text("first\n")
    tail = FileTail()
    tail.open(path)
    grown = (b"y" * 99 + b"\n") * (TAIL_BYTES // 100) + b"z" * (TAIL_BYTES % 100)
    append(path, grown)
    tail.follow()
    assert text(screen) == "first\n" + grown.decode()


def test_an_unchanged_file_writes_nothing_more(tmp_path: Path) -> None:
    path = tmp_path / "progress.log"
    path.write_text("x" * 300 + "\n")
    with (
        mock.patch.object(FileTail, "write") as write,
        mock.patch.object(FileTail, "clear") as clear,
        mock.patch.object(
            FileTail,
            "is_vertical_scroll_end",
            new_callable=mock.PropertyMock,
            return_value=True,
        ),
    ):
        tail = FileTail()
        tail.open(path)
        tail.follow()
    assert write.call_args_list == [
        mock.call(PROMPT, scroll_end=False),
        mock.call("x" * 300 + "\n", scroll_end=True),
    ]
    assert clear.call_count == 2


def test_appends_a_small_growth_to_a_file_near_the_tail_size(
    screen: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "progress.log"
    start = (b"w" * 99 + b"\n") * 655 + b"v" * 29 + b"\n"
    path.write_bytes(start)
    tail = FileTail()
    tail.open(path)
    append(path, b"more lines\n")
    tail.follow()
    assert text(screen) == start.decode() + "more lines\n"


@pytest.mark.parametrize("new", [b"two\n", b"two\nthree\n"])
def test_starts_over_when_the_file_is_replaced(
    screen: list[str], tmp_path: Path, new: bytes
) -> None:
    path = tmp_path / "progress.log"
    path.write_bytes(b"one\n")
    tail = FileTail()
    tail.open(path)
    staged = tmp_path / "staged.log"
    staged.write_bytes(new)
    staged.replace(path)
    tail.follow()
    assert text(screen) == new.decode()
