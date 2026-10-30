import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil


def test_sighup_stops_child_and_records_run(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        f"command = \"{sys.executable} -c 'import time; time.sleep(600)'\"\n"
    )
    command = [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(tmp_path / ".labnotes.toml"),
        "experiments",
        "exp",
        "run",
    ]
    process = subprocess.Popen(
        command,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    child_pid = None
    try:
        for _ in range(200):
            records = list(tmp_path.glob("exp/runs/*/run.json"))
            if records:
                record = json.loads(records[0].read_text())
                if record.get("pid"):
                    child_pid = record["pid"]
                    break
            time.sleep(0.05)
        assert child_pid is not None, "run did not start"
        children = [
            child_pid,
            *(
                child.pid
                for child in psutil.Process(child_pid).children(recursive=True)
            ),
        ]
        process.send_signal(signal.SIGHUP)
        output, _ = process.communicate(timeout=15)
        assert process.returncode is not None, output
        record = json.loads(records[0].read_text())
        assert record["ended_by"] == "stop", record
        assert record["ended"] is not None
        assert not psutil.pid_exists(child_pid), f"child {child_pid} survived"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for pid in locals().get("children", []):
            if psutil.pid_exists(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


def test_run_leaves_no_daemon_socket_or_lock(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} -c pass"\n'
    )
    command = [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(tmp_path / ".labnotes.toml"),
        "experiments",
        "exp",
        "run",
    ]
    result = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(tmp_path.rglob("*.sock"))
    assert not list(tmp_path.rglob("*.lock"))
    assert not any(
        "daemon" in " ".join(info.info["cmdline"]).lower()
        and str(tmp_path) in " ".join(info.info["cmdline"])
        for info in psutil.process_iter(["cmdline"])
        if info.pid != os.getpid() and info.info["cmdline"]
    )
