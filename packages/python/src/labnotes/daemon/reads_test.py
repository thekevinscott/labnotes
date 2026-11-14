import asyncio
import codecs
import json
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from labnotes.daemon.reads import TAIL_BYTES, Reads


def change(table: str, path: str | None = None, old: str | None = None) -> Any:
    return SimpleNamespace(
        table=table,
        row=None if path is None else {"path": path},
        old_row=None if old is None else {"path": old},
    )


def fake(
    queries: list[object] | None = None,
    steps: list[tuple[Callable[[], object], Any]] | None = None,
) -> mock.Mock:
    async def watch() -> AsyncIterator[Any]:
        for action, event in steps or []:
            action()
            yield event

    tables = mock.Mock()
    tables.ready = mock.AsyncMock()
    tables.query = mock.AsyncMock(side_effect=queries or [])
    tables.watch = mock.Mock(side_effect=lambda: watch())
    return tables


def request(last: str | None = None, **params: str) -> mock.Mock:
    return mock.Mock(
        headers={} if last is None else {"last-event-id": last}, path_params=params
    )


def parse(frames: list[str]) -> list[tuple[str, str, Any]]:
    parsed = []
    for frame in frames:
        fields = dict(line.split(": ", 1) for line in frame.splitlines() if line)
        parsed.append((fields["event"], fields["id"], json.loads(fields["data"])))
    return parsed


async def drain(response: Any) -> list[tuple[str, str, Any]]:
    assert response.media_type == "text/event-stream"
    return parse([str(frame) async for frame in response.body_iterator])


def nothing() -> None:
    return None


def test_state_id_ignores_order_and_follows_content() -> None:
    first = Reads.state_id({"a": {"x": 1, "y": 2}, "b": {}})
    assert first == Reads.state_id({"b": {}, "a": {"y": 2, "x": 1}})
    assert first != Reads.state_id({"a": {"x": 1, "y": 3}, "b": {}})
    assert len(first) == 16


def test_binary_spots_nul_bytes_and_invalid_utf8_but_not_a_cut_character() -> None:
    assert Reads.binary(b"plain\ntext\n") is False
    assert Reads.binary("café".encode()[:-1]) is False
    assert Reads.binary(b"a\0b") is True
    assert Reads.binary(b"\xff\xfe") is True
    assert Reads.binary(b"") is False


def test_offset_leaves_out_held_back_bytes() -> None:
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    assert decoder.decode("aé".encode()[:-1]) == "a"
    assert Reads.offset(2, decoder) == "1"


def test_read_returns_one_byte_range(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"0123456789")
    assert Reads.read(path, 2, 5) == b"234"


def test_tail_of_a_long_file_starts_after_a_newline(tmp_path: Path) -> None:
    path = tmp_path / "log"
    lines = "".join(f"line {number}\n" for number in range(20_000))
    path.write_text(lines)
    size = path.stat().st_size
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    text = Reads(tmp_path, fake()).tail(path, size, decoder)
    assert text.startswith("line ")
    assert text.endswith("line 19999\n")
    assert lines.endswith(text)
    assert TAIL_BYTES - len("line 19999\n") < len(text) <= TAIL_BYTES


def test_tail_of_a_short_file_is_all_of_it(tmp_path: Path) -> None:
    path = tmp_path / "log"
    path.write_text("one\ntwo")
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    assert Reads(tmp_path, fake()).tail(path, 7, decoder) == "one\ntwo"


def test_tail_without_any_newline_keeps_the_whole_window(tmp_path: Path) -> None:
    path = tmp_path / "log"
    path.write_text("x" * (TAIL_BYTES + 10))
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    text = Reads(tmp_path, fake()).tail(path, TAIL_BYTES + 10, decoder)
    assert text == "x" * TAIL_BYTES


def test_follow_sends_state_then_changes_and_ignores_other_tables() -> None:
    a, b = {"id": "a", "v": 1}, {"id": "b", "v": 1}
    a2, c = {"id": "a", "v": 2}, {"id": "c", "v": 1}
    rows = mock.AsyncMock(side_effect=[[a, b], [a2, c]])
    steps = [(nothing, change("logs")), (nothing, change("runs"))]
    tables = fake(steps=steps)
    reads = Reads(Path("/"), tables)

    events = asyncio.run(drain(reads.follow(request(), rows, "id", "run", {"runs"})))

    assert events == [
        ("state", Reads.state_id({"a": a, "b": b}), [a, b]),
        ("remove", Reads.state_id({"a": a}), {"id": "b"}),
        ("run", Reads.state_id({"a": a2}), a2),
        ("run", Reads.state_id({"a": a2, "c": c}), c),
    ]
    assert rows.await_count == 2
    tables.ready.assert_awaited_once()


def test_follow_skips_the_state_a_resuming_client_holds() -> None:
    a = {"id": "a"}
    rows = mock.AsyncMock(side_effect=[[a], [a]])
    reads = Reads(Path("/"), fake(steps=[(nothing, change("runs"))]))
    held = Reads.state_id({"a": a})

    events = asyncio.run(
        drain(reads.follow(request(held), rows, "id", "run", {"runs"}))
    )

    assert events == []


def test_follow_sends_state_to_a_client_with_an_old_id() -> None:
    a = {"id": "a"}
    rows = mock.AsyncMock(side_effect=[[a]])
    reads = Reads(Path("/"), fake())

    events = asyncio.run(
        drain(reads.follow(request("old"), rows, "id", "run", {"runs"}))
    )

    assert events == [("state", Reads.state_id({"a": a}), [a])]


def test_runs_names_each_run_without_its_stamp_and_follows_run_tables() -> None:
    found = [
        {"id": "20261114-000001-quiet-pond", "status": "running"},
        {"id": "sweep/20261114-000002-red-hill"},
        {"id": "plain"},
    ]
    tables = fake(queries=[found])
    reads = Reads(Path("/"), tables)
    with mock.patch.object(reads, "follow") as follow:
        asyncio.run(reads.runs(request()))
    [(_, rows, key, kind, names)] = [call.args for call in follow.call_args_list]
    assert (key, kind, set(names)) == ("id", "run", {"runs", "memory", "run_files"})
    assert asyncio.run(rows()) == [
        {"id": "20261114-000001-quiet-pond", "status": "running", "name": "quiet-pond"},
        {"id": "sweep/20261114-000002-red-hill", "name": "red-hill"},
        {"id": "plain", "name": "plain"},
    ]


def test_a_path_with_no_known_run_before_files_is_not_found() -> None:
    tables = fake(queries=[[], []])
    reads = Reads(Path("/"), tables)
    for path in ("nope/files", "files", "r/stop"):
        response = asyncio.run(reads.run_path(request(path=path)))
        assert response.status_code == 404
    assert [call.args[1] for call in tables.query.await_args_list] == [["nope"]]


def test_files_lists_names_sizes_and_mtimes_under_the_run_folder() -> None:
    tables = fake(
        queries=[
            [{"folder": "exp/runs/r"}],
            [{"name": "a.txt", "size": 3, "mtime_ns": 1_700_000_000_500_000_000}],
        ]
    )
    reads = Reads(Path("/"), tables)
    with (
        mock.patch.object(reads, "follow") as follow,
        mock.patch("labnotes.daemon.reads.iso_time", lambda at: f"at {at}"),
    ):
        asyncio.run(reads.run_path(request(path="r/files")))
        listed = asyncio.run(follow.call_args.args[1]())
    [(_, _, key, kind, names)] = [call.args for call in follow.call_args_list]
    assert (key, kind, set(names)) == ("name", "file", {"run_files"})
    assert listed == [{"name": "a.txt", "size": 3, "mtime": "at 1700000000.5"}]
    assert tables.query.await_args_list[0].args[1] == ["r"]
    assert tables.query.await_args_list[1].args[1] == {"folder": "exp/runs/r"}


def test_an_unlisted_file_is_not_found() -> None:
    tables = fake(queries=[[{"folder": "exp/runs/r"}], []])
    reads = Reads(Path("/"), tables)
    response = asyncio.run(reads.run_path(request(path="r/files/a")))
    assert response.status_code == 404
    assert tables.query.await_args_list[1].args == (
        "SELECT 1 FROM run_files WHERE path = ?",
        ["exp/runs/r/a"],
    )


def test_a_file_under_a_files_folder_belongs_to_the_first_known_run(
    tmp_path: Path,
) -> None:
    (tmp_path / "exp/runs/r/artifacts/files").mkdir(parents=True)
    (tmp_path / "exp/runs/r/artifacts/files/result.txt").write_text("hi\n")
    tables = fake(queries=[[{"folder": "exp/runs/r"}], [{"1": 1}]])
    reads = Reads(tmp_path, tables)
    response = asyncio.run(
        reads.run_path(request(path="r/files/artifacts/files/result.txt"))
    )
    assert asyncio.run(drain(response)) == [
        (
            "state",
            "3",
            {"name": "artifacts/files/result.txt", "size": 3, "text": "hi\n"},
        )
    ]
    assert [call.args[1] for call in tables.query.await_args_list] == [
        ["r"],
        ["exp/runs/r/artifacts/files/result.txt"],
    ]


def test_a_run_id_may_hold_a_files_segment() -> None:
    tables = fake(queries=[[], [{"folder": "exp/runs/a/files/b"}], [{"1": 1}]])
    reads = Reads(Path("/"), tables)
    with mock.patch.object(reads, "follow_file") as follow:
        asyncio.run(reads.run_path(request("7", path="a/files/b/files/x")))
    follow.assert_called_once_with("exp/runs/a/files/b/x", "x", "7")
    assert [call.args[1] for call in tables.query.await_args_list][:2] == [
        ["a"],
        ["a/files/b"],
    ]


def follow_file(
    tmp_path: Path,
    name: str,
    steps: list[tuple[Callable[[], object], Any]],
    last: str | None = None,
) -> list[tuple[str, str, Any]]:
    reads = Reads(tmp_path, fake(steps=steps))

    async def collect() -> list[str]:
        return [frame async for frame in reads.follow_file(name, name, last)]

    return parse(asyncio.run(collect()))


def test_text_file_sends_its_tail_then_appends(tmp_path: Path) -> None:
    log = tmp_path / "out.log"
    log.write_bytes(b"one\n")

    def append(data: bytes) -> Callable[[], object]:
        return lambda: log.open("ab").write(data)

    events = follow_file(
        tmp_path,
        "out.log",
        [
            (append(b"two\n"), change("run_files", "out.log")),
            (append(b"x"), change("logs", "out.log")),
            (nothing, change("run_files", "other.log")),
            (append("é".encode()[:1]), change("run_files", "out.log")),
            (append("é".encode()[1:]), change("run_files", None, "out.log")),
            (nothing, change("run_files", "out.log")),
            (lambda: log.write_bytes(b"new\n"), change("run_files", "out.log")),
            (log.unlink, change("run_files", None, "out.log")),
        ],
    )

    assert events == [
        ("state", "4", {"name": "out.log", "size": 4, "text": "one\n"}),
        ("append", "8", {"text": "two\n"}),
        ("append", "9", {"text": "x"}),
        ("append", "11", {"text": "é"}),
        ("state", "4", {"name": "out.log", "size": 4, "text": "new\n"}),
        ("remove", "4", {"name": "out.log"}),
    ]


def test_text_file_resumes_from_the_last_event_id(tmp_path: Path) -> None:
    (tmp_path / "out.log").write_bytes(b"one\ntwo\n")
    assert follow_file(tmp_path, "out.log", [], "4") == [
        ("append", "8", {"text": "two\n"})
    ]
    assert follow_file(tmp_path, "out.log", [], "8") == []


def test_text_file_ignores_an_id_it_cannot_resume_from(tmp_path: Path) -> None:
    (tmp_path / "out.log").write_bytes(b"one\n")
    state = [("state", "4", {"name": "out.log", "size": 4, "text": "one\n"})]
    assert follow_file(tmp_path, "out.log", [], "9") == state
    assert follow_file(tmp_path, "out.log", [], "abc") == state


def test_binary_file_sends_size_and_type_on_each_change(tmp_path: Path) -> None:
    image = tmp_path / "plot.png"
    image.write_bytes(b"\x89PNG\0")

    events = follow_file(
        tmp_path,
        "plot.png",
        [
            (nothing, change("run_files", "plot.png")),
            (
                lambda: image.write_bytes(b"\x89PNG\0more"),
                change("run_files", "plot.png"),
            ),
        ],
    )

    assert events == [
        ("state", "5", {"name": "plot.png", "size": 5, "type": "image/png"}),
        ("state", "9", {"name": "plot.png", "size": 9, "type": "image/png"}),
    ]


def test_binary_file_of_unknown_type_and_a_resumed_binary(tmp_path: Path) -> None:
    (tmp_path / "blob").write_bytes(b"\0\1")
    assert follow_file(tmp_path, "blob", []) == [
        ("state", "2", {"name": "blob", "size": 2, "type": "application/octet-stream"})
    ]
    assert follow_file(tmp_path, "blob", [], "2") == []


def test_a_rewritten_text_file_sends_fresh_state(tmp_path: Path) -> None:
    log = tmp_path / "run.json"
    log.write_bytes(b"aaaa\n")

    def replace(data: bytes) -> Callable[[], object]:
        def swap() -> None:
            fresh = tmp_path / "fresh"
            fresh.write_bytes(data)
            fresh.replace(log)

        return swap

    events = follow_file(
        tmp_path,
        "run.json",
        [
            (lambda: log.write_bytes(b"bbbb\n"), change("run_files", "run.json")),
            (lambda: log.write_bytes(b"cccc\nmore\n"), change("run_files", "run.json")),
            (replace(b"cccc\nmore\n"), change("run_files", "run.json")),
        ],
    )

    assert events == [
        ("state", "5", {"name": "run.json", "size": 5, "text": "aaaa\n"}),
        ("state", "5", {"name": "run.json", "size": 5, "text": "bbbb\n"}),
        ("state", "10", {"name": "run.json", "size": 10, "text": "cccc\nmore\n"}),
        ("state", "10", {"name": "run.json", "size": 10, "text": "cccc\nmore\n"}),
    ]


def test_a_resumed_text_file_appends_what_it_missed_then_follows(
    tmp_path: Path,
) -> None:
    log = tmp_path / "out.log"
    log.write_bytes(b"one\ntwo\n")
    events = follow_file(
        tmp_path,
        "out.log",
        [(lambda: log.open("ab").write(b"three\n"), change("run_files", "out.log"))],
        "4",
    )
    assert events == [
        ("append", "8", {"text": "two\n"}),
        ("append", "14", {"text": "three\n"}),
    ]


def test_a_removed_binary_file_says_so_and_ends(tmp_path: Path) -> None:
    image = tmp_path / "plot.png"
    image.write_bytes(b"\x89PNG\0")
    events = follow_file(
        tmp_path,
        "plot.png",
        [
            (nothing, change("logs", "plot.png")),
            (image.unlink, change("run_files", None, "plot.png")),
            (nothing, change("run_files", "plot.png")),
        ],
    )
    assert events == [
        ("state", "5", {"name": "plot.png", "size": 5, "type": "image/png"}),
        ("remove", "5", {"name": "plot.png"}),
    ]


def test_a_binary_rewritten_at_the_same_size_sends_state(tmp_path: Path) -> None:
    image = tmp_path / "plot.png"
    image.write_bytes(b"\x89PNG\0")

    def rewrite() -> None:
        image.write_bytes(b"\x89PNG\1")
        os.utime(image, ns=(1, 1))

    events = follow_file(
        tmp_path, "plot.png", [(rewrite, change("run_files", "plot.png"))], "5"
    )
    assert events == [
        ("state", "5", {"name": "plot.png", "size": 5, "type": "image/png"})
    ]


def test_a_cut_character_waits_for_its_last_byte(tmp_path: Path) -> None:
    log = tmp_path / "out.log"
    log.write_bytes(b"a\n")

    def append(data: bytes) -> Callable[[], object]:
        return lambda: log.open("ab").write(data)

    events = follow_file(
        tmp_path,
        "out.log",
        [
            (append("é".encode()[:1]), change("run_files", "out.log")),
            (append("é".encode()[1:]), change("run_files", "out.log")),
        ],
    )

    assert events == [
        ("state", "2", {"name": "out.log", "size": 2, "text": "a\n"}),
        ("append", "4", {"text": "é"}),
    ]
