import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

# The first launch leaves a checkpoint and fails; the next resumes from it.
SCRIPT = """
import os
import sys
import time
from pathlib import Path

checkpoint = Path(os.environ["LABNOTES_RUN"]) / "checkpoint.txt"
if checkpoint.exists():
    print("resumed from", checkpoint.read_text(), flush=True)
    time.sleep(60)
    sys.exit(0)
checkpoint.write_text("step 20")
print("saved step 20", flush=True)
sys.exit(1)
"""


def test_uvx_output_view_shows_every_invocation_labeled(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = true\ncommand = "{sys.executable} script.py"\n'
    )
    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    tui.quit(term)

    term = tui(root, "experiments", "exp", "run", cols=120)
    expect(term.get_by_text("1 at a time")).to_be_visible(timeout=60)
    term.key_enter()
    expect(term.get_by_text("resumed from step 20")).to_be_visible(timeout=60)
    expect(term.get_by_text("saved step 20")).to_be_visible()
    expect(term.get_by_text("── invocation 1 ·")).to_be_visible()
    expect(term.get_by_text("── invocation 2 ·")).to_be_visible()
    expect(term.get_by_text("stdout (2)")).to_be_visible()
    tui.stop(term)
