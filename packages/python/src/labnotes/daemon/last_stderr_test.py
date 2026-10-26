import asyncio
from pathlib import Path

import pytest

from labnotes.daemon.last_stderr import last_stderr


@pytest.mark.parametrize(
    ("log", "line"),
    [
        (b"Traceback\nValueError: boom\n\n  \n", "ValueError: boom"),
        (b"first\r\nlast\r\n", "last"),
        (b"no newline", "no newline"),
        (b" 10%\r 50%\r100%\r\n", "100%"),
        (b"ends mid-bar\r", "ends mid-bar"),
        (b"bad \xff byte\n", "bad \ufffd byte"),
        (b"", None),
        (b"\n \r\n\t\n", None),
    ],
)
def test_finds_the_last_non_blank_stderr_line(
    tmp_path: Path, log: bytes, line: str | None
) -> None:
    (tmp_path / "stderr.log").write_bytes(log)

    assert asyncio.run(last_stderr(tmp_path)) == line


def test_finds_nothing_without_a_stderr_log(tmp_path: Path) -> None:
    assert asyncio.run(last_stderr(tmp_path)) is None


@pytest.mark.parametrize(("blanks", "line"), [(49, "kept"), (50, None)])
def test_looks_back_fifty_lines(tmp_path: Path, blanks: int, line: str | None) -> None:
    (tmp_path / "stderr.log").write_bytes(b"kept\n" + b"\n" * blanks)

    assert asyncio.run(last_stderr(tmp_path)) == line
