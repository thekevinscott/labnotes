import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.run_output import run_output

RUN = {"folder": "alpha/runs/r1", "ended": None, "exit_code": None}


def built(text: str) -> str:
    # A string made at runtime, so `is` against a literal fails where `==` holds.
    return "".join(list(text))


def event(table: str, **row: object) -> mock.Mock:
    fields = {key: built(v) if isinstance(v, str) else v for key, v in row.items()}
    return mock.Mock(table=built(table), row=fields)


def log(
    rows: int, lines: int, stream: str = "stdout", file: str = "", fresh: bool = False
) -> str:
    name = file or f"{stream}.log"
    message = {
        "stream": stream,
        "file": name,
        "fresh": fresh,
        "rows": rows,
        "lines": lines,
    }
    return f"data: {json.dumps(message)}\n\n"


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
        log(1, 1, fresh=True),
        log(1, 1, "stderr", fresh=True),
        log(2, 2),
        log(3, 3),
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

    assert messages == [log(0, 0, fresh=True), log(1, 1), end(0)]


def test_sends_a_finished_run_without_waiting(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    loaded.return_value = {**RUN, "ended": "t", "exit_code": 1}
    (folder / "stderr.log").write_text("boom")

    assert collect(tmp_path, []) == [log(1, 0, "stderr", fresh=True), end(1)]


def test_sends_nothing_for_an_unknown_run(
    tmp_path: Path, loaded: mock.AsyncMock
) -> None:
    loaded.return_value = None

    assert collect(tmp_path, []) == []


def test_counts_each_stream_apart_while_one_is_mid_line(
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
        log(1, 0, fresh=True),
        log(1, 0),
        log(1, 1, "stderr", fresh=True),
        log(1, 1),
        end(0),
    ]


def test_finishes_with_what_is_on_disk_if_the_watch_stops(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    stdout = folder / "stdout.log"
    stdout.write_text("")

    messages = collect(
        tmp_path,
        [(lambda: append(stdout, b"late\n"), mock.Mock(table="files", row=None))],
    )

    assert messages == [log(0, 0, fresh=True), log(1, 1), end(None)]


def test_reads_only_on_its_own_runs_events(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    stdout = folder / "stdout.log"
    stdout.write_text("")

    def later(data: bytes) -> Step:
        return lambda: append(stdout, data)

    ours = {"experiment": "alpha", "run": "r1", "stream": "stdout"}
    messages = collect(
        tmp_path,
        [
            (later(b"a"), event("files", **ours)),
            (later(b"b"), event("logs", **{**ours, "run": "r0"})),
            (later(b"c"), event("logs", **{**ours, "run": "r2"})),
            (later(b"d"), event("logs", **{**ours, "experiment": "aardvark"})),
            (later(b"e"), event("logs", **{**ours, "experiment": "beta"})),
            (later(b"f\n"), event("logs", **ours)),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r0", ended="t", exit_code=1),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r2", ended="t", exit_code=1),
            ),
            (
                lambda: None,
                event("zzz", experiment="alpha", id="r1", ended="t", exit_code=1),
            ),
            (later(b"g\n"), event("logs", **ours)),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
            (later(b"after\n"), event("logs", **ours)),
        ],
    )

    assert messages == [log(0, 0, fresh=True), log(1, 1), log(2, 2), end(0)]


def test_counts_a_line_once_it_ends(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    stdout = folder / "stdout.log"
    stdout.write_text("")

    messages = collect(
        tmp_path,
        [
            (
                lambda: append(stdout, b"50%"),
                event("logs", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: append(stdout, b" 60%\n"),
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [log(0, 0, fresh=True), log(1, 0), log(1, 1), end(0)]


def block(record: dict[str, object]) -> str:
    return f"event: block\ndata: {json.dumps(record)}\n\n"


def test_sends_each_whole_block_line_as_it_is_logged(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    blocks = folder / "log.jsonl"
    stdout = folder / "stdout.log"
    stdout.write_text("")
    whole = json.dumps({"id": "t", "phase": "delta", "content": "✓"}).encode()
    blocks.write_bytes(b'not json\n{"content": "a"}\n[1]\n' + whole[:-3])
    printed = event("logs", experiment="alpha", run="r1", stream="stdout")
    logged = event("blocks", experiment="alpha", run="r1")

    messages = collect(
        tmp_path,
        [
            (lambda: append(stdout, b"x\n"), printed),
            (lambda: append(blocks, whole[-3:]), logged),
            (lambda: append(blocks, b"\n"), logged),
            (lambda: append(stdout, b"y\n"), printed),
            (
                lambda: append(blocks, b'{"content": "last"}\n'),
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [
        log(0, 0, fresh=True),
        block({"content": "a"}),
        log(1, 1),
        block({"id": "t", "phase": "delta", "content": "✓"}),
        log(2, 2),
        block({"content": "last"}),
        end(0),
    ]


def test_keeps_sending_blocks_past_invalid_utf8(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    blocks = folder / "log.jsonl"
    blocks.write_bytes(
        b'{"content":"ok"}\n{"content":"bad \xff"}\n{"content":"after"}\n'
    )

    messages = collect(
        tmp_path,
        [
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [
        block({"content": "ok"}),
        block({"content": "bad \ufffd"}),
        block({"content": "after"}),
        end(0),
    ]


def test_holds_a_first_block_line_until_it_ends(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    blocks = folder / "log.jsonl"
    blocks.write_bytes(b'{"content": "a"')

    messages = collect(
        tmp_path,
        [
            (
                lambda: append(blocks, b"}\n"),
                event("blocks", experiment="alpha", run="r1"),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [block({"content": "a"}), end(0)]


def test_reads_the_block_log_only_on_its_own_runs_events(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    blocks = folder / "log.jsonl"
    stdout = folder / "stdout.log"
    blocks.write_text("")
    stdout.write_text("")

    def later(content: str) -> Step:
        line = json.dumps({"content": content}) + "\n"
        return lambda: append(blocks, line.encode())

    def printed(text: bytes) -> tuple[Step, mock.Mock]:
        return (
            lambda: append(stdout, text),
            event("logs", experiment="alpha", run="r1", stream="stdout"),
        )

    messages = collect(
        tmp_path,
        [
            (later("a"), event("blocks", experiment="alpha", run="r2")),
            (later("b"), event("blocks", experiment="alpha", run="r0")),
            (later("c"), event("blocks", experiment="beta", run="r1")),
            (later("d"), event("aardvark", experiment="alpha", run="r1")),
            printed(b"x\n"),
            (later("e"), event("blocks", experiment="alpha", run="r1")),
            printed(b"y\n"),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [
        log(0, 0, fresh=True),
        log(1, 1),
        *(block({"content": c}) for c in "abcde"),
        log(2, 2),
        end(0),
    ]


def test_moves_to_the_newest_invocation_log_from_its_start(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    (folder / "stdout-20261102-090000-000000.txt").write_text("first\n")
    later = folder / "stdout-20261102-100000-000000.txt"

    def switch() -> None:
        later.write_text("second\n")
        (folder / "run.json").write_text(
            json.dumps({"invocations": [{"stdout": later.name}]})
        )

    (folder / "run.json").write_text(
        json.dumps({"invocations": [{"stdout": "stdout-20261102-090000-000000.txt"}]})
    )

    messages = collect(
        tmp_path,
        [
            (
                switch,
                event("logs", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [
        log(1, 1, file="stdout-20261102-090000-000000.txt", fresh=True),
        log(1, 1, file="stdout-20261102-100000-000000.txt", fresh=True),
        end(0),
    ]


def test_resets_offset_when_new_log_path_sorts_before_previous(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    previous = folder / "stdout.log"
    previous.write_text("long previous output\n")
    current = folder / "stdout-20261103-120000-000000.txt"
    assert current < previous

    def switch() -> None:
        current.write_text("new\n")
        (folder / "run.json").write_text(
            json.dumps({"invocations": [{"stdout": current.name}]})
        )

    messages = collect(
        tmp_path,
        [
            (
                switch,
                event("logs", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [
        log(1, 1, fresh=True),
        log(1, 1, file=current.name, fresh=True),
        end(0),
    ]


def test_rereads_a_log_that_shrinks(
    tmp_path: Path, folder: Path, loaded: mock.AsyncMock
) -> None:
    log_file = folder / "stdout.log"
    log_file.write_text("long previous output\n")

    messages = collect(
        tmp_path,
        [
            (
                lambda: log_file.write_text("new\n"),
                event("logs", experiment="alpha", run="r1", stream="stdout"),
            ),
            (
                lambda: None,
                event("runs", experiment="alpha", id="r1", ended="t", exit_code=0),
            ),
        ],
    )

    assert messages == [log(1, 1, fresh=True), log(1, 1, fresh=True), end(0)]
