import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx2
import pytest

from labnotes.tables.iso_time import iso_time

DONE = "20261114-000001-quiet-pond"
LIVE = "20261114-000002-red-hill"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256))


def inotify_watches(pid: int) -> int:
    watches = 0
    for fd in os.listdir(f"/proc/{pid}/fd"):
        try:
            if os.readlink(f"/proc/{pid}/fd/{fd}") != "anon_inode:inotify":
                continue
            info = Path(f"/proc/{pid}/fdinfo/{fd}").read_text()
        except FileNotFoundError:
            continue
        watches += sum(line.startswith("inotify wd:") for line in info.splitlines())
    return watches


def settled(pid: int, expected: int) -> None:
    for _ in range(50):
        if inotify_watches(pid) == expected:
            return
        time.sleep(0.1)
    assert inotify_watches(pid) == expected


def folders(path: Path) -> int:
    return 1 + sum(1 for found in path.rglob("*") if found.is_dir())


def size(folder: Path) -> int:
    return sum(found.stat().st_size for found in folder.rglob("*") if found.is_file())


def write_run(root: Path, run: str, record: dict[str, object]) -> Path:
    folder = root / "exp/runs" / run
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "run.json").write_text(json.dumps({"params": {}, **record}))
    return folder


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text('continues = false\ncommand = "true"\n')
    for name in ("a", "b", "c"):
        (root / f"data/{name}/deep/more").mkdir(parents=True)
    (root / "beta/files").mkdir(parents=True)
    (root / "beta/files/notes.md").write_text("beta notes\n")
    done = write_run(
        root,
        DONE,
        {"created": "2026-11-14T00:00:01Z", "ended": "2026-11-14T00:00:05Z"}
        | {"exit_code": 0},
    )
    (done / "stdout.log").write_text("one\ntwo\n")
    (done / "image.png").write_bytes(PNG)
    (done / "memory.jsonl").write_text(
        json.dumps({"time": 1.0, "rss": 1024, "processes": 1})
        + "\n"
        + json.dumps({"time": 2.0, "rss": 2048, "processes": 1})
        + "\n"
    )
    live = write_run(root, LIVE, {"created": "2026-11-14T00:00:02Z"})
    (live / "stdout.log").write_text("starting\n")
    return root


@pytest.fixture
def daemon(root: Path) -> Iterator[tuple[Path, int]]:
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        process = subprocess.Popen(
            [
                str(Path(sys.executable).parent / "labnotes"),
                "-c",
                str(root / ".labnotes.toml"),
                "daemon",
                "exp",
            ],
            cwd=root,
            env={**os.environ, "XDG_RUNTIME_DIR": runtime},
            stdout=subprocess.DEVNULL,
        )
        try:
            for _ in range(200):
                sockets = list(Path(runtime).glob("labnotes/*.sock"))
                if sockets:
                    break
                time.sleep(0.05)
            [path] = sockets
            yield path, process.pid
        finally:
            process.terminate()
            process.wait(timeout=15)


class Stream:
    """One open read route, read event by event."""

    def __init__(self, path: Path, route: str, last: str | None = None) -> None:
        self.client = httpx2.Client(
            transport=httpx2.HTTPTransport(uds=str(path)),
            base_url="http://labnotes",
            timeout=10,
        )
        headers = {} if last is None else {"Last-Event-ID": last}
        self.response = self.client.send(
            self.client.build_request("GET", route, headers=headers), stream=True
        )
        assert self.response.status_code == 200, self.response.read()
        assert self.response.headers["content-type"].startswith("text/event-stream")
        self.events = iter(httpx2.EventSource(self.response))

    def next(self) -> tuple[str, str, object]:
        event = next(self.events)
        assert event.id, event
        return event.event, event.id, event.json()

    def close(self) -> None:
        self.response.close()
        self.client.close()

    def __enter__(self) -> "Stream":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def run_row(root: Path, run: str, **fields: object) -> dict[str, object]:
    return {
        "id": run,
        "name": run.split("-", 2)[2],
        "size": size(root / "exp/runs" / run),
        **fields,
    }


def test_runs_streams_every_run_then_each_change(
    daemon: tuple[Path, int], root: Path
) -> None:
    with Stream(daemon[0], "/runs") as runs:
        name, first, state = runs.next()
        assert name == "state"
        assert state == [
            run_row(
                root,
                DONE,
                started="2026-11-14T00:00:01Z",
                status="succeeded",
                memory=2048,
            ),
            run_row(
                root,
                LIVE,
                started="2026-11-14T00:00:02Z",
                status="running",
                memory=None,
            ),
        ]

        (root / "exp/runs" / LIVE / "stdout.log").write_text("starting\nmore\n")
        name, second, changed = runs.next()
        assert name == "run"
        assert second != first
        assert changed == run_row(
            root, LIVE, started="2026-11-14T00:00:02Z", status="running", memory=None
        )

        write_run(
            root,
            LIVE,
            {"created": "2026-11-14T00:00:02Z", "ended": "2026-11-14T00:00:09Z"}
            | {"exit_code": 1},
        )
        while (event := runs.next())[0] == "run" and event[2]["status"] == "running":  # type: ignore[index]
            pass
        assert event[0] == "run"
        assert event[2]["status"] == "failed"  # type: ignore[index]


def test_files_streams_each_file_with_size_and_mtime_then_changes(
    daemon: tuple[Path, int], root: Path
) -> None:
    folder = root / "exp/runs" / DONE
    with Stream(daemon[0], f"/runs/{DONE}/files") as files:
        name, _, state = files.next()
        assert name == "state"
        assert state == [
            {
                "name": found.name,
                "size": found.stat().st_size,
                "mtime": iso_time(found.stat().st_mtime),
            }
            for found in sorted(folder.iterdir())
        ]

        (folder / "result.txt").write_text("42\n")
        name, _, added = files.next()
        assert (name, added) == (
            "file",
            {
                "name": "result.txt",
                "size": 3,
                "mtime": iso_time((folder / "result.txt").stat().st_mtime),
            },
        )

        (folder / "result.txt").unlink()
        assert files.next()[0::2] == ("remove", {"name": "result.txt"})


def test_file_streams_its_tail_then_appended_lines(
    daemon: tuple[Path, int], root: Path
) -> None:
    log = root / "exp/runs" / LIVE / "stdout.log"
    with Stream(daemon[0], f"/runs/{LIVE}/files/stdout.log") as tail:
        assert tail.next() == (
            "state",
            "9",
            {"name": "stdout.log", "size": 9, "text": "starting\n"},
        )
        with log.open("a") as out:
            out.write("step 1\n")
        assert tail.next() == ("append", "16", {"text": "step 1\n"})


def test_file_tail_of_a_long_log_starts_on_a_line(
    daemon: tuple[Path, int], root: Path
) -> None:
    log = root / "exp/runs" / LIVE / "stdout.log"
    log.write_text("".join(f"line {number}\n" for number in range(100_000)))
    with Stream(daemon[0], f"/runs/{LIVE}/files/stdout.log") as tail:
        name, _, state = tail.next()
    assert name == "state"
    assert state["size"] == log.stat().st_size  # type: ignore[index]
    text = state["text"]  # type: ignore[index]
    assert 0 < len(text) < log.stat().st_size
    assert text.startswith("line ")
    assert text.endswith("line 99999\n")


def test_binary_file_returns_size_and_type_not_content(
    daemon: tuple[Path, int], root: Path
) -> None:
    with Stream(daemon[0], f"/runs/{DONE}/files/image.png") as image:
        assert image.next() == (
            "state",
            str(len(PNG)),
            {"name": "image.png", "size": len(PNG), "type": "image/png"},
        )


def test_unknown_run_or_file_is_not_found(daemon: tuple[Path, int]) -> None:
    with httpx2.Client(
        transport=httpx2.HTTPTransport(uds=str(daemon[0])),
        base_url="http://labnotes",
        timeout=10,
    ) as http:
        assert http.get("/runs/nope/files").status_code == 404
        assert http.get(f"/runs/{DONE}/files/nope.txt").status_code == 404
        assert http.get(f"/runs/{DONE}/files/%2E%2E/run.json").status_code == 404


def test_reconnecting_with_last_event_id_resumes(
    daemon: tuple[Path, int], root: Path
) -> None:
    path = daemon[0]
    with Stream(path, "/runs") as runs:
        _, seen, _ = runs.next()
    with Stream(path, "/runs", seen) as runs:
        time.sleep(0.5)
        (root / "exp/runs" / DONE / "later.txt").write_text("x")
        name, _, changed = runs.next()
        assert name == "run"
        assert changed["id"] == DONE  # type: ignore[index]
    with Stream(path, "/runs", seen) as runs:
        assert runs.next()[0] == "state"

    log = root / "exp/runs" / LIVE / "stdout.log"
    with Stream(path, f"/runs/{LIVE}/files/stdout.log") as tail:
        _, offset, _ = tail.next()
    with log.open("a") as out:
        out.write("while away\n")
    with Stream(path, f"/runs/{LIVE}/files/stdout.log", offset) as tail:
        assert tail.next() == ("append", "20", {"text": "while away\n"})


def test_more_clients_add_no_watches_beyond_the_experiment(
    daemon: tuple[Path, int], root: Path
) -> None:
    path, pid = daemon
    with Stream(path, "/runs") as first:
        first.next()
        settled(pid, folders(root / "exp"))
        with (
            Stream(path, "/runs") as second,
            Stream(path, f"/runs/{DONE}/files") as files,
            Stream(path, f"/runs/{LIVE}/files/stdout.log") as tail,
        ):
            for stream in (second, files, tail):
                stream.next()
            time.sleep(1)
            assert inotify_watches(pid) == folders(root / "exp")
