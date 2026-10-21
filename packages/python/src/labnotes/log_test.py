import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.log import log, now


@pytest.fixture
def log_path() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.log.log_path") as log_path:
        yield log_path


def read_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_appends_one_line_per_call(tmp_path: Path, log_path: mock.MagicMock) -> None:
    path = tmp_path / "log.jsonl"
    log_path.return_value = path

    with mock.patch(
        "labnotes.log.now", side_effect=["2026-10-21T00:00:00.000Z", "later"]
    ):
        log({"id": "t1", "phase": "start", "type": "thinking"})
        log({"id": "t1", "phase": "delta", "content": "chunk"})

    assert read_lines(path) == [
        {
            "id": "t1",
            "phase": "start",
            "type": "thinking",
            "timestamp": "2026-10-21T00:00:00.000Z",
        },
        {"id": "t1", "phase": "delta", "content": "chunk", "timestamp": "later"},
    ]


def test_labnotes_sets_the_timestamp(tmp_path: Path, log_path: mock.MagicMock) -> None:
    path = tmp_path / "log.jsonl"
    log_path.return_value = path

    with mock.patch("labnotes.log.now", return_value="mine"):
        log({"content": "x", "timestamp": "theirs"})

    assert read_lines(path) == [{"content": "x", "timestamp": "mine"}]


def test_keeps_one_block_on_one_line(tmp_path: Path, log_path: mock.MagicMock) -> None:
    path = tmp_path / "log.jsonl"
    log_path.return_value = path

    log({"content": "two\nlines ü"})

    assert len(path.read_text().splitlines()) == 1
    assert read_lines(path)[0]["content"] == "two\nlines ü"


def test_prints_content_without_a_runner(
    log_path: mock.MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    log_path.return_value = None

    log({"content": "final answer"})
    log({"id": "t1", "phase": "start"})

    assert capsys.readouterr().out == "final answer\n"


def test_stamps_utc_with_milliseconds() -> None:
    stamp = now()

    assert len(stamp) == len("2026-10-21T00:00:00.000Z")
    assert stamp.endswith("Z")
