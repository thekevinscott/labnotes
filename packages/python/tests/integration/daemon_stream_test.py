import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import IO

import psutil
import pytest
from curtaincall import expect


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / "project" / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (cmdline := process.info["cmdline"] or []) and "daemon" in cmdline
    ]
    for process in owners:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owners, timeout=15)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


def labnotes(root: Path, *args: str) -> list[str]:
    return [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(root / ".labnotes.toml"),
        *args,
    ]


def project(tmp_path: Path, extra: str = "") -> tuple[Path, Path]:
    """A cell that prints once, then waits until the test creates release."""
    root = tmp_path / "project"
    release = tmp_path / "release"
    hold = tmp_path / "hold.py"
    hold.write_text(
        "import pathlib, time\n"
        "print('working', flush=True)\n"
        f"while not pathlib.Path({str(release)!r}).exists():\n"
        "    time.sleep(0.1)\n"
    )
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = '{sys.executable} {hold}'\n{extra}"
    )
    return root, release


def wait_for_socket(runtime: Path) -> Path:
    for _ in range(200):
        sockets = list(runtime.glob("labnotes/*.sock"))
        if sockets:
            return sockets[0]
        time.sleep(0.05)
    raise AssertionError("daemon socket did not appear")


def request(path: Path, message: dict[str, object]) -> dict[str, object]:
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(30)
        client.connect(str(path))
        client.sendall((json.dumps(message) + "\n").encode())
        with client.makefile("r") as replies:
            for line in replies:
                reply = json.loads(line)
                if "step" not in reply:
                    return reply
    raise AssertionError("daemon closed without a reply")


class Attached:
    """One attach connection, read line by line."""

    def __init__(self, path: Path) -> None:
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(10)
        self.socket.connect(str(path))
        self.socket.sendall(b'{"command":"attach"}\n')
        self.lines: IO[str] = self.socket.makefile("r")
        reply = json.loads(self.lines.readline())
        assert reply["ok"] is True, reply

    def next(self) -> dict[str, object]:
        try:
            line = self.lines.readline()
        except TimeoutError:
            raise AssertionError("daemon streamed nothing to the attached client")
        assert line, "daemon closed the attach connection"
        return json.loads(line)

    def take(self, count: int) -> list[dict[str, object]]:
        messages = [self.next() for _ in range(count)]
        for message in messages:
            assert set(message) == {"batch", "event"}, message
        return messages

    def until(self, batch: str, name: str) -> list[dict[str, object]]:
        """Collect streamed events up to one with this name for this batch."""
        seen: list[dict[str, object]] = []
        while True:
            message = self.next()
            assert set(message) == {"batch", "event"}, message
            event = message["event"]
            assert isinstance(event, dict)
            seen.append(message)
            if message["batch"] == batch and event["event"] == name:
                return seen

    def close(self) -> None:
        self.lines.close()
        self.socket.close()


def test_attached_clients_get_replay_then_deltas(tmp_path: Path, runtime: Path) -> None:
    root, release = project(tmp_path, "[params]\nm = ['a', 'b', 'c']\n")
    env = {
        **os.environ,
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(tmp_path / "state"),
    }
    daemon = subprocess.Popen(
        labnotes(root, "daemon", "exp"), cwd=root, env=env, stdout=subprocess.PIPE
    )
    clients: list[Attached] = []
    observer: Attached | None = None
    recorded: dict[str, list[object]] = {}

    def start(value: str) -> str:
        reply = request(path, {"command": "start", "options": {"only": {"m": [value]}}})
        assert reply["ok"] is True, reply
        batch = str(reply["batch"])
        assert observer is not None
        for message in observer.until(batch, "started"):
            recorded.setdefault(str(message["batch"]), []).append(message["event"])
        return batch

    def assert_replay(client: Attached, batches: list[str]) -> None:
        expected = {batch: recorded[batch] for batch in batches}
        replay = client.take(sum(len(events) for events in expected.values()))
        for batch, events in expected.items():
            assert [m["event"] for m in replay if m["batch"] == batch] == events

    try:
        path = wait_for_socket(runtime)
        observer = Attached(path)
        active = [start("a"), start("b")]

        clients = [Attached(path), Attached(path)]
        for client in clients:
            assert_replay(client, active)

        later = start("c")
        for client in clients:
            streamed = client.until(later, "started")
            names = [m["event"]["event"] for m in streamed if m["batch"] == later]  # type: ignore[index]
            assert names[0] == "planned", names

        late = Attached(path)
        clients.append(late)
        assert_replay(late, [*active, later])

        release.touch()
        for client in clients:
            ended = set()
            while ended != {*active, later}:
                message = client.next()
                if message["event"]["event"] == "idle":  # type: ignore[index]
                    ended.add(str(message["batch"]))
    finally:
        release.touch()
        for client in clients:
            client.close()
        if observer is not None:
            observer.close()
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)


def test_run_tui_shows_state_with_no_journal_on_disk(terminal, tmp_path: Path) -> None:
    root, release = project(tmp_path)
    state = tmp_path / "state"
    term = terminal(
        " ".join(labnotes(root, "experiments", "exp", "run")),
        rows=30,
        cols=160,
        env={"XDG_STATE_HOME": str(state)},
    )
    try:
        expect(term.get_by_text("working")).to_be_visible(timeout=30)
        assert not list(state.rglob("*.jsonl"))
        release.touch()
        expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=30)
        assert not term.get_by_text("Traceback").is_visible(), term.to_snapshot()
    finally:
        release.touch()


def test_lost_daemon_shows_disconnected_and_keeps_last_state(
    terminal, tmp_path: Path
) -> None:
    root, release = project(tmp_path)
    config = str(root / ".labnotes.toml")
    term = terminal(
        " ".join(labnotes(root, "experiments", "exp", "run")),
        rows=30,
        cols=160,
        env={"XDG_STATE_HOME": str(tmp_path / "state")},
    )
    try:
        expect(term.get_by_text("working")).to_be_visible(timeout=30)
        expect(term.get_by_text("1 at a time")).to_be_visible()
        for process in psutil.process_iter(["cmdline"]):
            cmdline = process.info["cmdline"] or []
            if config in cmdline and "daemon" in cmdline:
                process.send_signal(signal.SIGKILL)
        expect(term.get_by_text("disconnected")).to_be_visible(timeout=15)
        expect(term.get_by_text("working")).to_be_visible()
        expect(term.get_by_text("1 at a time")).to_be_visible()
        for key in ("+", "d"):
            term.write(key)
            time.sleep(0.5)
        expect(term.get_by_text("disconnected")).to_be_visible()
        assert term.is_alive, term.to_snapshot()
        assert not term.get_by_text("Traceback").is_visible(), term.to_snapshot()
    finally:
        release.touch()
