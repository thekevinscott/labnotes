import sys
import time
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SETUP = """
import time
from pathlib import Path

print("setting up", flush=True)
while not Path("set-up").exists():
    time.sleep(0.05)
with open("journal.txt", "a") as journal:
    journal.write("setup done\\n")
"""

RUN = """
import time

with open("journal.txt", "a") as journal:
    journal.write("start\\n")
time.sleep(1)
with open("journal.txt", "a") as journal:
    journal.write("end\\n")
"""


def journal(root: Path) -> list[str]:
    path = root / "journal.txt"
    return path.read_text().splitlines() if path.exists() else []


def test_uvx_minus_during_setup_waits_for_setup_then_runs_one_at_a_time(
    tmp_path: Path, tui: Tui
) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "setup.py").write_text(SETUP)
    (tmp_path / "run.py").write_text(RUN)
    (tmp_path / "exp/experiment.toml").write_text(
        f'continues = false\nrepeats = 3\ncommand = "{sys.executable} run.py"\n'
        f'setup = "{sys.executable} setup.py"\n'
    )
    term = tui(tmp_path, "experiments", "exp", "run", "--concurrency", "2")

    try:
        expect(term.get_by_text("setting up")).to_be_visible(timeout=60)
        expect(term.get_by_text("2 at a time")).to_be_visible()
        term.write("-")
        expect(term.get_by_text("1 at a time")).to_be_visible()
        time.sleep(2)
        assert journal(tmp_path) == []
        assert not list(tmp_path.glob("exp/runs/*"))
    finally:
        (tmp_path / "set-up").touch()

    expect(term.get_by_text("3 passed, 0 failed")).to_be_visible(timeout=60)
    assert journal(tmp_path) == ["setup done"] + ["start", "end"] * 3
    tui.quit(term)
