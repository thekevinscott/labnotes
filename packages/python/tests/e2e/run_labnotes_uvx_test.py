import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_records_the_labnotes_version_and_command_line(
    tmp_path: Path, uvx: dict[str, str], tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} -c pass"\ncontinues = false\n[params]\nm = ["a", "b"]\n'
    )
    argv = ["experiments", "exp", "run", "--m=b", "--", "--auth", "api key"]

    term = tui(root, *argv)
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    tui.quit(term)

    version = subprocess.run(
        ["uvx", "labnotes", "--version"],
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[-1]
    [record] = root.glob("exp/runs/**/run.json")
    run = json.loads(record.read_text())
    assert run["labnotes_version"] == version
    config = ["-c", str(root / ".labnotes.toml")]
    assert run["labnotes_command"] == shlex.join(["labnotes", *config, *argv])
