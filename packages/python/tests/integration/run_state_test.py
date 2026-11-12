import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
import pytest
from curtaincall import expect


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def daemons(root: Path) -> list[psutil.Process]:
    config = str(root / ".labnotes.toml")
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (cmdline := process.info["cmdline"] or []) and "daemon" in cmdline
    ]


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    (tmp_path / "release").touch()
    owners = daemons(tmp_path / "project")
    for process in owners:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(owners, timeout=15)


def labnotes(root: Path, *args: str) -> list[str]:
    return [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(root / ".labnotes.toml"),
        *args,
    ]


def run_state() -> Path:
    return Path(os.environ["XDG_STATE_HOME"]) / "labnotes" / "run-state"


def run_state_files() -> list[str]:
    return sorted(
        str(path.relative_to(run_state()))
        for path in run_state().rglob("*")
        if path.is_file()
    )


def wait_until(check, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "condition did not hold in time"
        time.sleep(0.05)


def request(path: Path, message: dict[str, object]) -> dict[str, object]:
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(30)
        client.connect(str(path))
        client.sendall((json.dumps(message) + "\n").encode())
        with client.makefile("r") as replies:
            for line in replies:
                reply = json.loads(line)
                if "step" not in reply:
                    return reply  # type: ignore[no-any-return]
    raise AssertionError("daemon closed without a reply")


def test_runs_write_no_journals_and_leave_run_state_as_it_was(
    terminal, tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    seen = []
    for repeats in (2, 4):
        (root / "exp/experiment.toml").write_text(
            f'continues = false\ncommand = "{sys.executable} -c pass"\n'
            f"repeats = {repeats}\n"
        )
        term = terminal(
            " ".join(labnotes(root, "experiments", "exp", "run")),
            rows=30,
            cols=120,
            env={"XDG_RUNTIME_DIR": str(runtime)},
        )
        expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=30)
        term.key_ctrl_c()
        assert term.wait(timeout=10) == 0, term.to_snapshot()
        wait_until(lambda: not daemons(root))
        seen.append(run_state_files())

    assert len(list(root.glob("exp/runs/*/run.json"))) == 4
    assert [name for name in seen[0] if name.endswith(".jsonl")] == []
    assert seen[1] == seen[0]


def test_daemon_names_each_batch_with_its_own_id(tmp_path: Path, runtime: Path) -> None:
    root = tmp_path / "project"
    release = tmp_path / "release"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    hold = tmp_path / "hold.py"
    hold.write_text(
        "import pathlib, time\n"
        f"while not pathlib.Path({str(release)!r}).exists():\n"
        "    time.sleep(0.1)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = '{sys.executable} {hold}'\n"
    )
    daemon = subprocess.Popen(
        labnotes(root, "daemon", "exp"),
        cwd=root,
        env={**os.environ, "XDG_RUNTIME_DIR": str(runtime)},
        stdout=subprocess.DEVNULL,
    )
    try:
        wait_until(lambda: bool(list(runtime.glob("labnotes/*.sock"))))
        [path] = runtime.glob("labnotes/*.sock")
        with socket.socket(socket.AF_UNIX) as observer:
            observer.settimeout(30)
            observer.connect(str(path))
            observer.sendall(b'{"command":"attach"}\n')
            with observer.makefile("r") as stream:
                assert json.loads(stream.readline()) == {"ok": True, "batches": []}

                started = request(path, {"command": "start", "options": {}})
                assert started["ok"] is True, started
                assert "journal" not in started
                batch = started["batch"]
                assert isinstance(batch, str) and batch
                assert "/" not in batch and not batch.endswith(".jsonl")

                listed = request(path, {"command": "batches"})
                assert listed == {"ok": True, "batches": [batch]}

                first = json.loads(stream.readline())
                assert first == {"batch": batch, "event": first["event"]}
                assert first["event"]["event"] == "planned"

        assert [p for p in run_state().rglob("*.jsonl")] == []
    finally:
        release.touch()
        if daemon.poll() is None:
            daemon.terminate()
        daemon.wait(timeout=15)
