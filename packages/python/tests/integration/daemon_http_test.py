import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx2
import pytest

from conftest import DaemonEvents, daemon_request


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[Path]:
    """A live daemon for an experiment whose one cell waits for release."""
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    release = tmp_path / "release"
    hold = tmp_path / "hold.py"
    hold.write_text(
        "import pathlib, time\n"
        f"while not pathlib.Path({str(release)!r}).exists():\n"
        "    time.sleep(0.1)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = '{sys.executable} {hold}'\n"
    )
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
            yield path
        finally:
            release.touch()
            process.terminate()
            process.wait(timeout=15)


def client(path: Path) -> httpx2.Client:
    return httpx2.Client(
        transport=httpx2.HTTPTransport(uds=str(path)),
        base_url="http://labnotes",
        timeout=30,
    )


def test_daemon_answers_http_on_its_socket(daemon: Path) -> None:
    assert daemon_request(daemon, "GET", "/batches") == {"ok": True, "batches": []}
    with client(daemon) as http:
        assert http.get("/nowhere").status_code == 404
        bad = http.post("/concurrency", content=b"not json")
        assert (bad.status_code, bad.json()) == (
            400,
            {"ok": False, "error": "Invalid request"},
        )
        rejected = http.post("/concurrency", json={"count": 0})
        assert rejected.status_code == 400
        assert rejected.json() == {"ok": False, "error": "count must be positive"}


def test_start_streams_steps_then_its_reply(daemon: Path) -> None:
    with client(daemon) as http:
        with http.sse("/start", method="POST", json={}) as source:
            events = list(source)
    assert [event.event for event in events[:-1]] == ["step"] * (len(events) - 1)
    assert "Preparing codebase" in [event.json() for event in events]
    reply = events[-1]
    assert reply.event == "reply"
    assert reply.json()["ok"] is True
    assert daemon_request(daemon, "GET", "/batches") == {
        "ok": True,
        "batches": [reply.json()["batch"]],
    }


def test_events_stream_names_batches_then_replays_and_follows(daemon: Path) -> None:
    with DaemonEvents(daemon) as before:
        assert before.batches == []
        started = daemon_request(daemon, "POST", "/start", {})
        batch = started["batch"]
        first = before.next()
        assert first["batch"] == batch
        assert first["event"]["event"] == "planned"  # type: ignore[index]
        with DaemonEvents(daemon) as late:
            assert late.batches == [batch]
            assert late.next() == first
        assert daemon_request(daemon, "POST", "/stop") == {"ok": True}
        names = []
        while "idle" not in names:
            names.append(before.next()["event"]["event"])  # type: ignore[index]
        assert "stopping" in names
