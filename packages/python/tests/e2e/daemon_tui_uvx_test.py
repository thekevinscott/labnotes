import json
import shlex

from curtaincall import Terminal, expect
import os
import pty
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

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


def signal_tui(process: subprocess.Popen[bytes], number: int) -> None:
    try:
        os.killpg(process.pid, number)
    except ProcessLookupError:
        pass


def test_uvx_tui_crash_keeps_run_alive(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(6)'\"\n"
    )
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [
                "uvx",
                "labnotes",
                "-c",
                str(root / ".labnotes.toml"),
                "experiments",
                "exp",
                "run",
            ],
            cwd=root,
            env={**os.environ, **uvx, "XDG_RUNTIME_DIR": runtime},
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
        )
        os.close(slave)
        try:
            for _ in range(200):
                paths = list(root.glob("exp/runs/*/run.json"))
                if paths:
                    record = json.loads(paths[0].read_text())
                    if record.get("pid") and not record.get("ended"):
                        break
                time.sleep(0.05)
            assert paths, "installed TUI did not start a cell"
            assert record["ended"] is None
            assert list(Path(runtime).glob("labnotes/*.sock"))
            signal_tui(process, signal.SIGKILL)
            process.wait(timeout=10)
            for _ in range(200):
                record = json.loads(paths[0].read_text())
                if record.get("ended"):
                    break
                time.sleep(0.05)
            assert record["exit_code"] == 0
        finally:
            os.close(master)
            if process.poll() is None:
                signal_tui(process, signal.SIGKILL)
                process.wait()


def test_uvx_frozen_tui_keeps_scheduling(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\nrepeats = 2\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(2)'\"\n"
    )
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        env={**os.environ, **uvx},
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )
    os.close(slave)
    try:
        for _ in range(200):
            paths = list(root.glob("exp/runs/*/run.json"))
            if len(paths) == 1 and json.loads(paths[0].read_text()).get("pid"):
                break
            time.sleep(0.02)
        assert len(paths) == 1
        assert json.loads(paths[0].read_text())["ended"] is None
        signal_tui(process, signal.SIGSTOP)
        for _ in range(150):
            paths = list(root.glob("exp/runs/*/run.json"))
            if len(paths) == 2 and all(
                json.loads(path.read_text()).get("ended") for path in paths
            ):
                break
            time.sleep(0.05)
        assert len(paths) == 2
        assert all(json.loads(path.read_text())["exit_code"] == 0 for path in paths)
    finally:
        signal_tui(process, signal.SIGCONT)
        signal_tui(process, signal.SIGKILL)
        process.wait(timeout=10)
        os.close(master)


def test_uvx_browse_restart_survives_tui_kill(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "marker").write_text("")
    (root / "script.py").write_text(
        "import sys, time\nfrom pathlib import Path\n"
        "if Path('marker').exists():\n    Path('marker').unlink()\n    sys.exit(1)\n"
        "time.sleep(3)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\ncontinues = false\nretries = 0\n'
    )
    base = ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "experiments", "exp"]
    first_runtime_dir = TemporaryDirectory(prefix="ln-runtime-")
    first_runtime = Path(first_runtime_dir.name)
    first = Terminal(
        shlex.join([*base, "run"]),
        rows=30,
        cols=120,
        env={**os.environ, **uvx, "XDG_RUNTIME_DIR": str(first_runtime)},
    )
    first.start()
    try:
        expect(first.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=30)
        first.key_ctrl_c()
        assert first.wait(timeout=10) == 0
    finally:
        first.kill()
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        master, slave = pty.openpty()
        process = subprocess.Popen(
            base,
            cwd=root,
            env={**os.environ, **uvx, "XDG_RUNTIME_DIR": runtime},
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
        )
        os.close(slave)
        try:
            time.sleep(1)
            os.write(master, b"r")
            for _ in range(200):
                paths = list(root.glob("exp/runs/*/run.json"))
                if len(paths) == 2 and any(
                    json.loads(path.read_text()).get("pid")
                    and not json.loads(path.read_text()).get("ended")
                    for path in paths
                ):
                    break
                time.sleep(0.05)
            assert len(paths) == 2
            assert list(Path(runtime).glob("labnotes/*.sock")) or list(
                first_runtime.glob("labnotes/*.sock")
            )
            signal_tui(process, signal.SIGKILL)
            process.wait(timeout=10)
            for _ in range(150):
                if all(json.loads(path.read_text()).get("ended") for path in paths):
                    break
                time.sleep(0.05)
            assert sorted(
                json.loads(path.read_text())["exit_code"] for path in paths
            ) == [0, 1]
        finally:
            if process.poll() is None:
                signal_tui(process, signal.SIGKILL)
            process.wait()
            os.close(master)


def test_uvx_second_tty_reuses_daemon_then_idle_daemon_exits(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(2)'\"\n"
    )
    base = [
        "uvx",
        "labnotes",
        "-c",
        str(root / ".labnotes.toml"),
        "experiments",
        "exp",
        "run",
    ]
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        env = {**os.environ, **uvx, "XDG_RUNTIME_DIR": runtime}
        first_master, first_slave = pty.openpty()
        first = subprocess.Popen(
            base,
            cwd=root,
            env=env,
            stdin=first_slave,
            stdout=first_slave,
            stderr=first_slave,
            start_new_session=True,
        )
        os.close(first_slave)
        second_master = None
        second = None
        try:
            for _ in range(200):
                sockets = list(Path(runtime).glob("labnotes/*.sock"))
                if sockets:
                    break
                time.sleep(0.05)
            assert len(sockets) == 1
            second_master, second_slave = pty.openpty()
            second = subprocess.Popen(
                base,
                cwd=root,
                env=env,
                stdin=second_slave,
                stdout=second_slave,
                stderr=second_slave,
                start_new_session=True,
            )
            os.close(second_slave)
            for _ in range(200):
                paths = list(root.glob("exp/runs/*/run.json"))
                if paths and all(
                    json.loads(path.read_text()).get("ended") for path in paths
                ):
                    break
                time.sleep(0.05)
            assert paths
            assert len(list(Path(runtime).glob("labnotes/*.sock"))) == 1
            time.sleep(5.5)
            assert sockets[0].exists()
            signal_tui(first, signal.SIGKILL)
            signal_tui(second, signal.SIGKILL)
            first.wait(timeout=10)
            second.wait(timeout=10)
            for _ in range(150):
                if not sockets[0].exists():
                    break
                time.sleep(0.05)
            assert not sockets[0].exists()
        finally:
            if first.poll() is None:
                signal_tui(first, signal.SIGKILL)
            first.wait()
            os.close(first_master)
            if second is not None:
                if second.poll() is None:
                    signal_tui(second, signal.SIGKILL)
                second.wait()
            if second_master is not None:
                os.close(second_master)
