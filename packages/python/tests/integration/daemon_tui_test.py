import json
import os
import pty
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import psutil
import pytest


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / "project" / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
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


@pytest.fixture
def runtime_env() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}):
            yield Path(runtime)


def launch_tty(root: Path, slave: int) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            str(Path(sys.executable).parent / "labnotes"),
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )


def records(root: Path) -> list[dict[str, object]]:
    return [json.loads(path.read_text()) for path in root.glob("exp/runs/*/run.json")]


def test_killed_tui_leaves_cell_running_and_finishing(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(2)'\"\n"
    )
    master, slave = pty.openpty()
    process = launch_tty(root, slave)
    os.close(slave)
    try:
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("pid"):
                break
            time.sleep(0.05)
        assert records, "TTY cell never started"
        process.kill()
        process.wait(timeout=10)
        for _ in range(100):
            record = json.loads(records[0].read_text())
            if record.get("ended"):
                break
            time.sleep(0.05)
        assert record["exit_code"] == 0
        assert record["ended_by"] is None
    finally:
        os.close(master)
        if process.poll() is None:
            process.send_signal(signal.SIGKILL)
            process.wait()


def test_frozen_tui_does_not_delay_queued_cell(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\nrepeats = 2\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(0.6)'\"\n"
    )
    master, slave = pty.openpty()
    process = launch_tty(root, slave)
    os.close(slave)
    try:
        for _ in range(100):
            if len(records(root)) == 1 and records(root)[0].get("pid"):
                break
            time.sleep(0.02)
        assert len(records(root)) == 1
        process.send_signal(signal.SIGSTOP)
        for _ in range(100):
            current = records(root)
            if len(current) == 2 and all(record.get("ended") for record in current):
                break
            time.sleep(0.05)
        assert len(current) == 2
        assert [record["exit_code"] for record in current] == [0, 0]
    finally:
        process.send_signal(signal.SIGCONT)
        process.kill()
        process.wait(timeout=10)
        os.close(master)


def test_second_tty_reuses_daemon_and_idle_disconnect_releases_it(
    tmp_path: Path,
    runtime_env: Path,
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(1)'\"\n"
    )
    first_master, first_slave = pty.openpty()
    first = launch_tty(root, first_slave)
    os.close(first_slave)
    second_master = second_slave = None
    second = None
    try:
        for _ in range(100):
            sockets = list(runtime_env.glob("labnotes/*.sock"))
            if sockets and records(root):
                break
            time.sleep(0.05)
        assert len(sockets) == 1
        second_master, second_slave = pty.openpty()
        second = launch_tty(root, second_slave)
        os.close(second_slave)
        second_slave = None
        for _ in range(100):
            if (
                len(list(runtime_env.glob("labnotes/*.sock"))) == 1
                and second.poll() is None
            ):
                break
            time.sleep(0.05)
        assert len(list(runtime_env.glob("labnotes/*.sock"))) == 1
        for _ in range(100):
            if records(root) and all(record.get("ended") for record in records(root)):
                break
            time.sleep(0.05)
        assert all(record["exit_code"] == 0 for record in records(root))
        time.sleep(5.5)
        assert sockets[0].exists(), "attached TUI should keep idle daemon alive"
        first.kill()
        second.kill()
        first.wait(timeout=10)
        second.wait(timeout=10)
        for _ in range(150):
            if not sockets[0].exists():
                break
            time.sleep(0.05)
        assert not sockets[0].exists()
    finally:
        if first.poll() is None:
            first.kill()
        first.wait(timeout=10)
        os.close(first_master)
        if second is not None:
            if second.poll() is None:
                second.kill()
            second.wait(timeout=10)
        if second_master is not None:
            os.close(second_master)
        if second_slave is not None:
            os.close(second_slave)
