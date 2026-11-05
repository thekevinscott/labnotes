import json
import os
import re
import shlex
import sys
from pathlib import Path

from curtaincall import Terminal, expect


def test_uvx_run_uses_a_relative_experiment_config_in_tui(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / "alt").mkdir()
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text('command = "false"\n')
    (root / "alt/experiment.toml").write_text(
        f"command = \"{sys.executable} -c 'print(317)'\"\ncontinues = false\n"
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
            "-e",
            "alt/experiment.toml",
        ]
    )
    terminal = Terminal(
        f"bash -c {shlex.quote(f'cd {shlex.quote(str(root))} && exec {command}')}",
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )
    terminal.start()
    try:
        expect(terminal.get_by_text(re.compile(r"1 passed, 0 failed\."))).to_be_visible(
            timeout=30
        )
        terminal.key_ctrl_c()
        assert terminal.wait(timeout=10) == 0
        [record] = [
            json.loads(path.read_text()) for path in root.glob("exp/runs/*/run.json")
        ]
        assert record["exit_code"] == 0
        [output] = root.glob("exp/runs/*/stdout.log")
        assert "317" in output.read_text()
    finally:
        terminal.kill()
