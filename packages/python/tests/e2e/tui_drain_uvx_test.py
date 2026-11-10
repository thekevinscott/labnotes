import json
import os
import re
import shlex
import sys
from pathlib import Path

from curtaincall import Terminal, expect


def test_installed_tui_drains_without_stopping_current_run(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\nrepeats = 2\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(2)'\"\n"
    )
    args = [
        "uvx",
        "labnotes",
        "-c",
        str(tmp_path / ".labnotes.toml"),
        "experiments",
        "exp",
        "run",
    ]
    term = Terminal(
        "/bin/sh -c "
        + shlex.quote(f"cd {shlex.quote(str(tmp_path))} && exec {shlex.join(args)}"),
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )
    term.start()
    try:
        expect(term.get_by_text("1 at a time")).to_be_visible(timeout=30)
        expect(term.get_by_text(re.compile(r"[|/\\-] +\d+s"))).to_be_visible()
        expect(term.get_by_text("Draining")).not_to_be_visible()
        term.write("d")
        expect(term.get_by_text("Draining")).to_be_visible()
        expect(term.get_by_text("1 passed, 0 failed")).to_be_visible(timeout=20)
        assert term.is_alive
        records = [
            json.loads(path.read_text())
            for path in tmp_path.glob("exp/runs/*/run.json")
        ]
        assert len(records) == 1
        assert records[0]["exit_code"] == 0
        assert records[0]["ended_by"] is None
        term.key_ctrl_c()
        term.wait(timeout=10)
    finally:
        term.kill()
