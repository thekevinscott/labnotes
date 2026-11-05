import json
import os
import re
import shlex
import sys
from pathlib import Path

from curtaincall import Terminal, expect


def test_uvx_run_completes_through_tui(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'print(1)'\"\n"
    )
    command = shlex.join(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ]
    )
    term = Terminal(command, rows=30, cols=120, env={**os.environ, **uvx})
    term.start()
    try:
        expect(term.get_by_text(re.compile(r"1 passed, 0 failed\."))).to_be_visible(
            timeout=30
        )
        term.key_ctrl_c()
        assert term.wait(timeout=10) == 0
        [record] = [
            json.loads(path.read_text()) for path in root.glob("exp/runs/*/run.json")
        ]
        assert record["exit_code"] == 0
    finally:
        term.kill()
