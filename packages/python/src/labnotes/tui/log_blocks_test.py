import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.log_blocks import LogBlocks


class FakeBlock:
    def __init__(self, body: str) -> None:
        self.body = body

    def extend(self, text: str) -> None:
        self.body += text


@pytest.fixture
def blocks() -> Iterator[LogBlocks]:
    with (
        mock.patch("labnotes.tui.log_blocks.LogBlock", FakeBlock),
        mock.patch("labnotes.tui.log_blocks.Static", FakeLabel, create=True),
        mock.patch.object(LogBlocks, "remove_children"),
        mock.patch.object(LogBlocks, "mount"),
    ):
        yield LogBlocks(id="blocks")


class FakeLabel:
    def __init__(self, text: str, classes: str = "") -> None:
        self.body = f"[{text}]"
        self.classes = classes


def bodies(blocks: LogBlocks) -> list[str]:
    return [call.args[0].body for call in getattr(blocks.mount, "call_args_list")]


def append(folder: Path, *records: object) -> None:
    with (folder / "log.jsonl").open("a", encoding="utf-8") as file:
        for record in records:
            text = record if isinstance(record, str) else json.dumps(record)
            file.write(f"{text}\n")


def test_starts_hidden_and_empty(blocks: LogBlocks) -> None:
    assert blocks.id == "blocks"
    assert not blocks.display
    assert blocks.read_to == 0


def test_follows_nothing_before_a_run_logs(tmp_path: Path, blocks: LogBlocks) -> None:
    blocks.follow(tmp_path)

    assert bodies(blocks) == []
    assert not blocks.display


def test_shows_a_complete_block(tmp_path: Path, blocks: LogBlocks) -> None:
    append(tmp_path, {"content": "answer", "timestamp": "t"})

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["answer"]
    assert blocks.display


def test_reads_only_new_lines_on_each_follow(tmp_path: Path, blocks: LogBlocks) -> None:
    append(tmp_path, {"content": "one"})
    blocks.follow(tmp_path)
    blocks.follow(tmp_path)
    append(tmp_path, {"content": "two"})
    blocks.follow(tmp_path)

    assert bodies(blocks) == ["one", "two"]


def test_waits_for_a_line_to_finish(tmp_path: Path, blocks: LogBlocks) -> None:
    line = json.dumps({"content": "café"}).encode()
    (tmp_path / "log.jsonl").write_bytes(line[:5])
    blocks.follow(tmp_path)
    assert bodies(blocks) == []

    with (tmp_path / "log.jsonl").open("ab") as file:
        file.write(line[5:] + b"\n")
    blocks.follow(tmp_path)

    assert bodies(blocks) == ["café"]


def test_grows_a_streaming_block_in_place(tmp_path: Path, blocks: LogBlocks) -> None:
    append(
        tmp_path,
        {"id": "t1", "phase": "start", "type": "thinking"},
        {"id": "t1", "phase": "delta", "content": "par"},
    )
    blocks.follow(tmp_path)
    assert bodies(blocks) == ["par"]

    append(
        tmp_path,
        {"id": "t1", "phase": "delta", "content": "tial"},
        {"id": "t1", "phase": "stop"},
    )
    blocks.follow(tmp_path)

    assert bodies(blocks) == ["partial"]


def test_keeps_streams_apart_by_id(tmp_path: Path, blocks: LogBlocks) -> None:
    append(
        tmp_path,
        {"id": "a", "phase": "start", "content": "A"},
        {"id": "b", "phase": "start", "content": "B"},
        {"id": "a", "phase": "delta", "content": "a"},
        {"content": "done"},
        {"id": "b", "phase": "delta", "content": "b"},
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["Aa", "Bb", "done"]


def test_opens_a_block_on_a_delta_without_start(
    tmp_path: Path, blocks: LogBlocks
) -> None:
    append(
        tmp_path,
        {"id": "t1", "phase": "delta", "content": "x"},
        {"id": "t1", "phase": "delta", "content": "y"},
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["xy"]


def test_starts_a_new_block_after_stop(tmp_path: Path, blocks: LogBlocks) -> None:
    append(
        tmp_path,
        {"id": "t1", "phase": "start", "content": "one"},
        {"id": "t1", "phase": "stop"},
        {"id": "t1", "phase": "stop"},
        {"id": "t1", "phase": "delta", "content": "two"},
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["one", "two"]


def test_shows_an_unknown_phase_as_a_complete_block(
    tmp_path: Path, blocks: LogBlocks
) -> None:
    append(
        tmp_path,
        {"id": "t1", "phase": "update", "content": "u"},
        {"id": "t1", "phase": "delta", "content": "d"},
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["u", "d"]


def test_skips_lines_that_are_not_blocks(tmp_path: Path, blocks: LogBlocks) -> None:
    append(tmp_path, "not json", "[1, 2]", "", {"content": 3})

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["3"]


def test_reset_forgets_the_last_run(tmp_path: Path, blocks: LogBlocks) -> None:
    append(tmp_path, {"id": "t1", "phase": "start", "content": "old"})
    blocks.follow(tmp_path)

    blocks.reset()
    blocks.follow(tmp_path / "missing")
    assert not blocks.display
    assert blocks.read_to == 0
    getattr(blocks.remove_children, "assert_called_with")()

    other = tmp_path / "other"
    other.mkdir()
    append(other, {"id": "t1", "phase": "delta", "content": "new"})
    blocks.follow(other)

    assert bodies(blocks) == ["old", "new"]


def test_keeps_reading_past_invalid_utf8(tmp_path: Path, blocks: LogBlocks) -> None:
    (tmp_path / "log.jsonl").write_bytes(
        b'{"content":"ok"}\n{"content":"bad \xff"}\n{"content":"after"}\n'
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["ok", "bad �", "after"]


def test_labels_each_invocations_blocks(tmp_path: Path, blocks: LogBlocks) -> None:
    append(
        tmp_path,
        {"content": "one", "invocation": "20261112-100000-000001"},
        {"content": "two", "invocation": "20261112-100000-000001"},
        {"content": "three", "invocation": "20261112-110500-000002"},
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == [
        "[invocation 2026-11-12 10:00:00]",
        "one",
        "two",
        "[invocation 2026-11-12 11:05:00]",
        "three",
    ]


def test_closes_a_block_a_dead_invocation_left_open(
    tmp_path: Path, blocks: LogBlocks
) -> None:
    append(
        tmp_path,
        {
            "id": "t1",
            "phase": "start",
            "content": "cut",
            "invocation": "20261112-100000-000001",
        },
        {
            "id": "t1",
            "phase": "delta",
            "content": "new",
            "invocation": "20261112-110500-000002",
        },
        {
            "id": "t1",
            "phase": "delta",
            "content": "er",
            "invocation": "20261112-110500-000002",
        },
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == [
        "[invocation 2026-11-12 10:00:00]",
        "cut",
        "[invocation 2026-11-12 11:05:00]",
        "newer",
    ]


def test_reset_forgets_the_last_invocation(tmp_path: Path, blocks: LogBlocks) -> None:
    append(tmp_path, {"content": "old", "invocation": "20261112-100000-000001"})
    blocks.follow(tmp_path)

    blocks.reset()
    other = tmp_path / "other"
    other.mkdir()
    append(other, {"content": "new", "invocation": "20261112-100000-000001"})
    blocks.follow(other)

    assert bodies(blocks) == [
        "[invocation 2026-11-12 10:00:00]",
        "old",
        "[invocation 2026-11-12 10:00:00]",
        "new",
    ]


def test_labels_only_invocations_labnotes_tagged(
    tmp_path: Path, blocks: LogBlocks
) -> None:
    append(
        tmp_path,
        {"content": "one", "invocation": "mine"},
        {"content": "two", "invocation": 7},
    )

    blocks.follow(tmp_path)

    assert bodies(blocks) == ["one", "two"]
