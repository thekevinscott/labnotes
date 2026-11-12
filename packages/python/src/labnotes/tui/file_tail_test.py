import asyncio
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult

from labnotes.tui.file_tail import SNIFF_BYTES, TAIL_BYTES, FileTail


class Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield FileTail(id="tail")


def drive(check: Callable[[FileTail], None]) -> None:
    async def run() -> None:
        async with Harness().run_test() as pilot:
            check(pilot.app.query_one(FileTail))

    asyncio.run(run())


def test_shows_nothing_until_a_file_is_opened() -> None:
    def check(tail: FileTail) -> None:
        tail.follow()
        assert tail.path is None
        assert tail.line_count == 0

    drive(check)


def test_shows_the_file_and_follows_appends(tmp_path: Path) -> None:
    path = tmp_path / "metrics.txt"
    path.write_text("step 1\nstep 2\n")

    def check(tail: FileTail) -> None:
        tail.open(path)
        assert list(tail.lines) == ["step 1", "step 2", ""]
        with path.open("a") as file:
            file.write("step 3\npart")
        tail.follow()
        assert list(tail.lines) == ["step 1", "step 2", "step 3", "part"]
        with path.open("a") as file:
            file.write("ial\n")
        tail.follow()
        assert list(tail.lines) == ["step 1", "step 2", "step 3", "partial", ""]
        tail.follow()
        assert tail.line_count == 4

    drive(check)


def test_reading_a_new_file_starts_over(tmp_path: Path) -> None:
    first, second = tmp_path / "a.txt", tmp_path / "b.txt"
    first.write_text("from a\n")
    second.write_text("from b\n")

    def check(tail: FileTail) -> None:
        tail.open(first)
        tail.open(second)
        assert tail.path == second
        assert list(tail.lines) == ["from b", ""]

    drive(check)


def test_shows_only_the_end_of_a_large_file(tmp_path: Path) -> None:
    path = tmp_path / "big.log"
    path.write_bytes(b"x" * TAIL_BYTES + b"\nlast line\n")

    def check(tail: FileTail) -> None:
        tail.open(path)
        assert tail.lines[0] == "[skipped 11 bytes]"
        assert tail.lines[-2] == "last line"
        assert tail.offset == path.stat().st_size

    drive(check)


def test_skips_a_large_append_to_its_end(tmp_path: Path) -> None:
    path = tmp_path / "big.log"
    path.write_text("first\n")

    def check(tail: FileTail) -> None:
        tail.open(path)
        with path.open("ab") as file:
            file.write(b"y" * (TAIL_BYTES + 6) + b"\nend\n")
        tail.follow()
        assert tail.lines[:2] == ["first", "[skipped 11 bytes]"]
        assert tail.lines[-2] == "end"

    drive(check)


def test_starts_over_when_the_file_shrinks(tmp_path: Path) -> None:
    path = tmp_path / "rewritten.log"
    path.write_text("a long first version\n")

    def check(tail: FileTail) -> None:
        tail.open(path)
        path.write_text("short\n")
        tail.follow()
        assert list(tail.lines) == ["short", ""]

    drive(check)


def test_shows_a_placeholder_for_a_binary_file(tmp_path: Path) -> None:
    path = tmp_path / "model.pt"
    path.write_bytes(b"PK\x00\x01" + b"\xff" * 100)

    def check(tail: FileTail) -> None:
        tail.open(path)
        assert list(tail.lines) == [
            "model.pt is binary (104 bytes), so it isn't shown."
        ]
        with path.open("ab") as file:
            file.write(b"\x00" * 896)
        tail.follow()
        assert list(tail.lines) == ["model.pt is binary (1.0 kB), so it isn't shown."]

    drive(check)


def test_sniffs_only_the_start_of_a_file_for_binary(tmp_path: Path) -> None:
    path = tmp_path / "late.log"
    path.write_bytes(b"a" * SNIFF_BYTES + b"\x00\n")

    def check(tail: FileTail) -> None:
        tail.open(path)
        assert "binary" not in tail.lines[0]

    drive(check)


def test_detects_binary_once_an_empty_file_gets_bytes(tmp_path: Path) -> None:
    path = tmp_path / "later.bin"
    path.write_bytes(b"")

    def check(tail: FileTail) -> None:
        tail.open(path)
        assert tail.line_count == 0
        path.write_bytes(b"\x00\x01")
        tail.follow()
        assert list(tail.lines) == ["later.bin is binary (2 bytes), so it isn't shown."]

    drive(check)


def test_decodes_characters_split_across_reads(tmp_path: Path) -> None:
    path = tmp_path / "accents.txt"
    encoded = "café\n".encode()
    path.write_bytes(encoded[:4])

    def check(tail: FileTail) -> None:
        tail.open(path)
        assert list(tail.lines) == ["caf"]
        path.write_bytes(encoded)
        tail.follow()
        assert list(tail.lines) == ["café", ""]

    drive(check)


def test_says_so_when_the_file_is_gone_and_reads_it_again_when_back(
    tmp_path: Path,
) -> None:
    path = tmp_path / "gone.txt"
    path.write_text("before\n")

    def check(tail: FileTail) -> None:
        tail.open(path)
        path.unlink()
        tail.follow()
        assert list(tail.lines) == ["gone.txt is gone."]
        path.write_text("after\n")
        tail.follow()
        assert list(tail.lines) == ["after", ""]

    drive(check)
