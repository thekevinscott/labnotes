import json
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

# The first launch opens a streaming block and dies; the second reuses its id.
SCRIPT = """
import os
import sys
from pathlib import Path

from labnotes import log

state = Path(os.environ["LABNOTES_RUN"]) / "state.txt"
first = not state.exists()
state.write_text("x")
if first:
    log({"id": "t1", "phase": "start", "content": "cut off"})
    sys.exit(1)
log({"id": "t1", "phase": "delta", "content": "fresh"})
"""


def label(stdout: str) -> str:
    stamp = stdout.removeprefix("stdout-")
    return f"invocation {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}"


def test_uvx_labels_each_invocations_blocks(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\ncontinues = true\n'
        '[params]\nm = ["a"]\n'
    )

    term = tui(root, "experiments", "exp", "run", rows=30, cols=120)
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    tui.quit(term)

    term = tui(root, "experiments", "exp", "run", rows=30, cols=120)
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    [path] = root.glob("exp/runs/**/run.json")
    first, second = json.loads(path.read_text())["invocations"]
    expect(term.get_by_text(label(first["stdout"]))).to_be_visible(timeout=30)
    expect(term.get_by_text(label(second["stdout"]))).to_be_visible()
    expect(term.get_by_text("▸ cut off")).to_be_visible()
    expect(term.get_by_text("▸ fresh")).to_be_visible()
    expect(term.get_by_text("cut offfresh")).not_to_be_visible()
    tui.quit(term)
