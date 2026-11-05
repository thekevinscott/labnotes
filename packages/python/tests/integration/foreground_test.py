import json
import os
import re
import shlex
import signal
import sys
import time
from pathlib import Path

from curtaincall import Terminal, expect

from labnotes.runner.run_locked import run_locked


def command(root: Path) -> str:
    return shlex.join(
        [
            str(Path(sys.executable).parent / "labnotes"),
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ]
    )


def test_sighup_of_tui_leaves_daemon_run_alive(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(2)'\"\n"
    )
    term = Terminal(command(tmp_path), rows=30, cols=120)
    term.start()
    try:
        for _ in range(100):
            records = list(tmp_path.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("pid"):
                break
            time.sleep(0.05)
        assert records
        assert term._child is not None
        os.kill(term._child.pid, signal.SIGHUP)
        term.wait(timeout=10)
        for _ in range(100):
            record = json.loads(records[0].read_text())
            if record.get("ended"):
                break
            time.sleep(0.05)
        assert record["exit_code"] == 0
    finally:
        term.kill()


def test_tui_run_releases_its_run_lock(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} -c pass"\n'
    )
    term = Terminal(command(tmp_path), rows=30, cols=120)
    term.start()
    try:
        expect(term.get_by_text(re.compile(r"1 passed, 0 failed\."))).to_be_visible(
            timeout=20
        )
        term.key_ctrl_c()
        assert term.wait(timeout=10) == 0
        locks = list(tmp_path.rglob("*.lock"))
        assert len(locks) == 1
        assert not run_locked(locks[0].parent)
    finally:
        term.kill()
