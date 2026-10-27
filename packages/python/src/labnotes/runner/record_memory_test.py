import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.record_memory import record_memory


class Stop(Exception):
    pass


@pytest.fixture
def clock() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.runner.record_memory.time.time", side_effect=[10.5, 15.5, 20.5]
    ) as clock:
        yield clock


def record(
    path: Path, usages: list[tuple[int, int] | None], *, container_bytes: int = 0
) -> list[list[str]]:
    seen: list[list[str]] = []
    pauses = iter(range(len(usages)))

    async def pause(seconds: float) -> None:
        assert seconds == 5.0
        seen.append(path.read_text(encoding="utf-8").splitlines())
        if next(pauses) == len(usages) - 1:
            raise Stop

    with (
        mock.patch(
            "labnotes.runner.record_memory.tree_usage", side_effect=usages
        ) as tree_usage,
        mock.patch("labnotes.runner.record_memory.asyncio.sleep", new=pause),
        mock.patch("labnotes.runner.record_memory.ContainerMemory") as containers,
        pytest.raises(Stop),
    ):
        containers.return_value.start = mock.AsyncMock()
        containers.return_value.close = mock.AsyncMock()
        containers.return_value.usage.return_value = container_bytes
        asyncio.run(record_memory(path, 42, 1234.5, 5.0))
    assert tree_usage.call_args_list == [mock.call(42, 1234.5)] * len(usages)
    containers.assert_called_once_with(path.parent.name)
    return seen


def test_writes_each_sample_as_a_line_before_waiting(
    tmp_path: Path, clock: mock.MagicMock
) -> None:
    path = tmp_path / "memory.jsonl"

    seen = record(path, [(100, 1), (300, 2)])

    first = {"time": 10.5, "rss": 100, "processes": 1}
    second = {"time": 15.5, "rss": 300, "processes": 2}
    assert [[json.loads(line) for line in lines] for lines in seen] == [
        [first],
        [first, second],
    ]


def test_skips_a_sample_when_the_tree_is_gone(
    tmp_path: Path, clock: mock.MagicMock
) -> None:
    path = tmp_path / "memory.jsonl"

    seen = record(path, [None, (300, 2)])

    assert seen[0] == []
    assert [json.loads(line) for line in seen[1]] == [
        {"time": 10.5, "rss": 300, "processes": 2}
    ]


def test_appends_to_samples_already_there(
    tmp_path: Path, clock: mock.MagicMock
) -> None:
    path = tmp_path / "memory.jsonl"
    path.write_text('{"rss": 1}\n', encoding="utf-8")

    seen = record(path, [(100, 1)])

    assert seen[0][0] == '{"rss": 1}'
    assert len(seen[0]) == 2


def test_adds_container_memory_without_counting_containers_as_processes(
    tmp_path: Path, clock: mock.MagicMock
) -> None:
    folder = tmp_path / "runs"
    folder.mkdir()
    seen = record(folder / "memory.jsonl", [(100, 2)], container_bytes=50)
    assert json.loads(seen[0][0]) == {"time": 10.5, "rss": 150, "processes": 2}
