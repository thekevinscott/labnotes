import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil


def test_uvx_sighup_stops_child_and_records_run(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"command = \"{sys.executable} -c 'import time; time.sleep(600)'\"\n"
    )
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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    child_pid = None
    try:
        for _ in range(300):
            records = list(root.glob("exp/runs/*/run.json"))
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
        output, _ = process.communicate(timeout=20)
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
