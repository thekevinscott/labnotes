import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from labnotes import log


def read_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_appends_one_line_per_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "log.jsonl"
    monkeypatch.setenv("LABNOTES_LOG", str(path))

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


def test_labnotes_sets_the_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "log.jsonl"
    monkeypatch.setenv("LABNOTES_LOG", str(path))

    with mock.patch("labnotes.log.now", return_value="mine"):
        log({"content": "x", "timestamp": "theirs"})

    assert read_lines(path) == [{"content": "x", "timestamp": "mine"}]


def test_keeps_one_block_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "log.jsonl"
    monkeypatch.setenv("LABNOTES_LOG", str(path))

    log({"content": "two\nlines"})

    assert len(path.read_text().splitlines()) == 1
    assert read_lines(path)[0]["content"] == "two\nlines"


def test_prints_content_without_a_runner(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("LABNOTES_LOG", raising=False)

    log({"content": "final answer"})
    log({"id": "t1", "phase": "start"})

    assert capsys.readouterr().out == "final answer\n"


def test_stamps_utc_with_milliseconds() -> None:
    from labnotes.log import now

    assert len(now()) == len("2026-10-21T00:00:00.000Z")
    assert now().endswith("Z")


def test_loads_only_the_standard_library() -> None:
    code = (
        "import sys\n"
        "before = set(sys.modules)\n"
        "from labnotes import log\n"
        "loaded = set(sys.modules) - before\n"
        "print('\\n'.join(sorted(loaded)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    loaded = result.stdout.split()
    first_party = {name for name in loaded if name.split(".")[0] == "labnotes"}
    third_party = {
        name.split(".")[0]
        for name in loaded
        if name.split(".")[0] not in sys.stdlib_module_names
        and name.split(".")[0] != "labnotes"
    }

    assert first_party == {"labnotes", "labnotes.log", "labnotes.log_path"}
    assert third_party == set()
