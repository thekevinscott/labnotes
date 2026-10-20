import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.run_output import run_output

RUN = {"folder": "alpha/runs/r1", "ended": None, "exit_code": None}


def event(table: str, **row: object) -> mock.Mock:
    return mock.Mock(table=table, row=row)


def log(text: str, stream: str = "stdout") -> str:
    return f"data: {json.dumps({'stream': stream, 'text': text})}\n\n"


def end(code: object) -> str:
    return f"event: end\ndata: {json.dumps(code)}\n\n"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    path = tmp_path / "alpha/runs/r1"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def loaded() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.run_output.load_run", new_callable=mock.AsyncMock
    ) as load_run:
        load_run.return_value = RUN
        yield load_run


def append(path: Path, data: bytes) -> None:
    with path.open("ab") as file:
        file.write(data)


Step = Callable[[], object]


def collect(
    root: Path, steps: list[tuple[Step, mock.Mock]], run: str = "r1"
) -> list[str]:
    async def events() -> AsyncIterator[mock.Mock]:
        for step, happened in steps:
            step()
            yield happened

    tables = mock.Mock()
    tables.watch.return_value = events()

    async def drain() -> list[str]:
        return [message async for message in run_output(tables, root, "alpha", run)]

    return asyncio.run(drain())


def test_streams_both_logs_then_follows_them_until_the_run_ends(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    (folder / "stdout.log").write_text("one\n")
    (folder / "stderr.log").write_text("warn\n")
    stdout = folder / "stdout.log"

    messages = collect(
        tmp_path,
        [
            (
                lambda: append(stdout, b"two\n"),
                event("logs", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: append(stdout, b"three\n"),
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=3),
            ),
        ],
    )

    assert messages == [
        log("one\n"),
        log("warn\n", "stderr"),
        log("two\n"),
        log("three\n"),
        end(3),
    ]
    loaded.assert_awaited_once_with(mock.ANY, "alpha", "r1")


def test_ignores_other_runs_and_experiments(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    stdout = folder / "stdout.log"
    stdout.write_text("")

    messages = collect(
        tmp_path,
        [
            (lambda: None, mock.Mock(table="files", row=None)),
            (
                lambda: append(stdout, b"a\n"),
                event("logs", experiment="beta", run="r1", stream="stdout"),
            ),
            (
                lambda: None,
                event("logs", experiment="alpha", run="r2", stream="stdout"),
            ),
            (
                lambda: None,
                event("runs", experiment="beta", id="r1", ended="t", exit_code=1),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r2", ended="t", exit_code=1),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended=None, exit_code=None),
            ),
            (
                lambda: None,
                event("files", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [log("a\n"), end(0)]


def test_sends_a_finished_run_without_waiting(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    loaded.return_value = {**RUN, "ended": "t", "exit_code": 1}
    (folder / "stderr.log").write_text("boom")

    assert collect(tmp_path, []) == [log("boom", "stderr"), end(1)]


def test_sends_nothing_for_an_unknown_run(
    tmp_path: Path, loaded: mock.AsyncMock
) -> None:
    loaded.return_value = None

    assert collect(tmp_path, []) == []


def test_breaks_an_unfinished_line_when_the_other_stream_writes(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    (folder / "stdout.log").write_text("50%")
    stderr = folder / "stderr.log"
    stdout = folder / "stdout.log"

    messages = collect(
        tmp_path,
        [
            (
                lambda: append(stdout, b" 60%"),
                event("logs", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: append(stderr, b"oops\n"),
                event("logs", experiment="alpha", run="r1", stream="stderr"),
            ),
            (
                lambda: append(stdout, b"done\n"),
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [
        log("50%"),
        log(" 60%"),
        log("\noops\n", "stderr"),
        log("done\n"),
        end(0),
    ]


def test_holds_a_character_split_across_writes(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    check = "✓".encode()
    stdout = folder / "stdout.log"
    stdout.write_bytes(check[:1])

    messages = collect(
        tmp_path,
        [
            (
                lambda: append(stdout, b""),
                event("logs", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: append(stdout, check[1:]),
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [log("✓"), end(0)]


def test_replaces_bytes_that_are_not_utf8(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    loaded.return_value = {**RUN, "ended": "t", "exit_code": 0}
    (folder / "stdout.log").write_bytes(b"\xffok")

    assert collect(tmp_path, [])[0] == log("�ok")


def test_finishes_with_what_is_on_disk_if_the_watch_stops(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    stdout = folder / "stdout.log"
    stdout.write_text("")

    messages = collect(
        tmp_path,
        [(lambda: append(stdout, b"late\n"), mock.Mock(table="files", row=None))],
    )

    assert messages == [log("late\n"), end(None)]
