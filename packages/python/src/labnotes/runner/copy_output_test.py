import asyncio
import io
import json
import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.copy_output import CHUNK_BYTES, copy_output


@pytest.fixture(autouse=True)
def clock() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.runner.copy_output.time.time", side_effect=lambda: 12.5
    ) as clock:
        yield clock


def entries(index: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in index.read_text().splitlines()]


def test_copies_each_chunk_and_records_where_it_ends(tmp_path: Path) -> None:
    read, write = os.pipe()

    async def go() -> None:
        with (
            (tmp_path / "stdout.log").open("wb") as log,
            (tmp_path / "output.jsonl").open("wb") as index,
        ):
            copying = asyncio.create_task(copy_output(read, "stdout", log, index))
            os.write(write, b"first\n")
            await asyncio.sleep(0.05)
            assert len(entries(tmp_path / "output.jsonl")) == 1
            os.write(write, b"second")
            await asyncio.sleep(0.05)
            os.close(write)
            await copying

    asyncio.run(go())

    assert (tmp_path / "stdout.log").read_bytes() == b"first\nsecond"
    assert entries(tmp_path / "output.jsonl") == [
        {"stream": "stdout", "end": 6, "time": 12.5},
        {"stream": "stdout", "end": 12, "time": 12.5},
    ]


def test_copies_a_large_write_in_bounded_chunks(tmp_path: Path) -> None:
    read, write = os.pipe()
    data = bytes(range(256)) * 2048

    async def go() -> None:
        with (
            (tmp_path / "stderr.log").open("wb") as log,
            (tmp_path / "output.jsonl").open("wb") as index,
        ):
            copying = asyncio.create_task(copy_output(read, "stderr", log, index))
            await asyncio.to_thread(os.write, write, data)
            os.close(write)
            await copying

    asyncio.run(go())

    assert (tmp_path / "stderr.log").read_bytes() == data
    ends = [int(str(entry["end"])) for entry in entries(tmp_path / "output.jsonl")]
    assert ends[-1] == len(data)
    sizes = [after - before for before, after in zip([0, *ends], ends, strict=False)]
    assert all(0 < size <= CHUNK_BYTES for size in sizes)
    assert len(ends) > 1


def test_writes_the_log_before_the_index_entry_that_points_into_it(
    tmp_path: Path,
) -> None:
    read, write = os.pipe()
    log_path = tmp_path / "stdout.log"
    seen: list[int] = []

    class Index(io.BytesIO):
        def write(self, data: object) -> int:
            seen.append(log_path.stat().st_size)
            return super().write(data)  # type: ignore[arg-type]

    async def go() -> None:
        with log_path.open("wb") as log:
            os.write(write, b"abc")
            os.close(write)
            await copy_output(read, "stdout", log, Index())

    asyncio.run(go())

    assert seen == [3]


def test_closes_the_pipe_when_cancelled(tmp_path: Path) -> None:
    read, write = os.pipe()

    async def go() -> None:
        with (
            (tmp_path / "stdout.log").open("wb") as log,
            (tmp_path / "output.jsonl").open("wb") as index,
        ):
            copying = asyncio.create_task(copy_output(read, "stdout", log, index))
            await asyncio.sleep(0.05)
            copying.cancel()
            await asyncio.wait({copying})

    asyncio.run(go())

    with pytest.raises(BrokenPipeError):
        os.write(write, b"late")
    os.close(write)


def test_reads_up_to_64_kib_at_a_time() -> None:
    assert CHUNK_BYTES == 65536
