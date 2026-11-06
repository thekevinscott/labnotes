import json
import os
import subprocess
import sys
import time
from pathlib import Path

from curtaincall import Terminal

from conftest import run_uvx_tui

# Takes a second to shut down on SIGTERM, then exits with its own code.
SCRIPT = """
import signal
import sys
import time
from pathlib import Path


def shut_down(*_):
    Path("term.txt").write_text(str(time.time()))
    time.sleep(1)
    sys.exit(3)


signal.signal(signal.SIGTERM, shut_down)
Path("started.txt").write_text("")
time.sleep(30)
"""


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "trap.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} trap.py"\n'
        "memory_interval = 0.1\n"
    )
    return root


def ended_run(root: Path) -> dict[str, object]:
    for _ in range(200):
        records = list(root.glob("exp/runs/*/run.json"))
        if records and json.loads(records[0].read_text()).get("ended"):
            break
        time.sleep(0.1)
    [record] = records
    return json.loads(record.read_text()) | {"folder": record.parent}


def assert_the_script_shut_down(root: Path, ended_by: str) -> None:
    run = ended_run(root)
    assert (run["exit_code"], run["signal"], run["ended_by"]) == (3, None, ended_by)
    term = float((root / "term.txt").read_text())
    folder = run["folder"]
    assert isinstance(folder, Path)
    samples = (folder / "memory.jsonl").read_text().splitlines()
    assert json.loads(samples[-1])["time"] > term + 0.8


def test_uvx_timeout_records_the_scripts_own_exit_code(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = make_project(tmp_path)

    run_uvx_tui(root, uvx, "experiments", "exp", "run", "--timeout", "1")

    assert_the_script_shut_down(root, "timeout")


def test_uvx_stop_records_the_scripts_own_exit_code(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = make_project(tmp_path)
    env = {**os.environ, **uvx}
    labnotes = ["uvx", "labnotes", "-c", str(root / ".labnotes.toml")]
    term = Terminal(" ".join([*labnotes, "experiments", "exp", "run"]), env=env)
    term.start()
    try:
        for _ in range(600):
            if (root / "started.txt").exists():
                break
            time.sleep(0.1)
        assert (root / "started.txt").exists()
        result = subprocess.run(
            [*labnotes, "experiments", "exp", "stop"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        ended_run(root)
    finally:
        term.kill()

    assert_the_script_shut_down(root, "stop")
