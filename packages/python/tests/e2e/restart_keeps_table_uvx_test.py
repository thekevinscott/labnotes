import sys
import time
from pathlib import Path

from curtaincall import expect

from conftest import Tui

CELL = """
import sys, time
from pathlib import Path

try:
    Path("fail-once").unlink()
    sys.exit(1)
except FileNotFoundError:
    pass
while not Path("release").exists():
    time.sleep(0.05)
"""
SPINNER = {"|", "/", "-", "\\"}


def screen(term) -> str:
    return "\n".join("".join(row) for row in term.get_viewable_buffer())


def status(shown: str, run: str) -> str:
    for row in shown.splitlines():
        if run in row and "--m " in row:
            return row.split(run, 1)[1].split()[2]
    return ""


def test_uvx_restart_keeps_the_runs_table_while_its_setup_reruns(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "cell.py").write_text(CELL)
    (root / "fail-once").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} cell.py"\n'
        'setup = "sleep 1"\nteardown = "true"\n'
        "continues = true\nretries = 0\nconcurrency = 10\n"
        '[params]\nm = ["a", "b", "c"]\n'
    )
    term = tui(root, "experiments", "exp", "run")
    try:
        expect(term.get_by_text("✗ exited 1")).to_be_visible(timeout=120)
        rows = screen(term).splitlines()
        runs = [row.split()[1] for row in rows if "--m " in row]
        [failed] = [row.split()[1] for row in rows if "✗ exited 1" in row]
        for _ in range(runs.index(failed)):
            term.key_down()
        term.write("r")
        seen = [screen(term)]
        while status(seen[-1], failed) not in SPINNER:
            shown = seen[-1]
            assert all(status(shown, run) for run in runs), shown
            assert "stdout (" not in shown, shown
            assert len(seen) < 400, shown
            time.sleep(0.05)
            seen.append(screen(term))
        term.key_enter()
        expect(term.get_by_text(f"exp — {failed}")).to_be_visible(timeout=5)
        term.key_escape()
        expect(term.get_by_text(failed)).to_be_visible()
    finally:
        (root / "release").write_text("")
    tui.quit(term)
