import signal
import sys
import time
from pathlib import Path

import psutil
from curtaincall import expect

from conftest import Tui


def project(tmp_path: Path) -> tuple[Path, Path]:
    """A cell that prints once, then waits until the test creates release."""
    root = tmp_path / "project"
    release = tmp_path / "release"
    hold = tmp_path / "hold.py"
    hold.write_text(
        "import pathlib, time\n"
        "print('working', flush=True)\n"
        f"while not pathlib.Path({str(release)!r}).exists():\n"
        "    time.sleep(0.1)\n"
    )
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = '{sys.executable} {hold}'\n"
    )
    return root, release


def test_uvx_run_tui_shows_state_without_reading_the_journal(
    tmp_path: Path, tui: Tui
) -> None:
    root, release = project(tmp_path)
    state = tmp_path / "state"
    term = tui(root, "experiments", "exp", "run", env={"XDG_STATE_HOME": str(state)})
    try:
        expect(term.get_by_text("working")).to_be_visible(timeout=60)
        journals = list(state.glob("labnotes/run-state/*/*.jsonl"))
        assert journals, "daemon wrote no journal"
        for journal in journals:
            journal.unlink()
        release.touch()
        expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=30)
    finally:
        release.touch()
    tui.quit(term)


def test_uvx_lost_daemon_shows_disconnected_and_keeps_last_state(
    tmp_path: Path, tui: Tui
) -> None:
    root, release = project(tmp_path)
    config = str(root / ".labnotes.toml")
    term = tui(
        root,
        "experiments",
        "exp",
        "run",
        env={"XDG_STATE_HOME": str(tmp_path / "state")},
    )
    try:
        expect(term.get_by_text("working")).to_be_visible(timeout=60)
        expect(term.get_by_text("1 at a time")).to_be_visible()
        for process in psutil.process_iter(["cmdline"]):
            cmdline = process.info["cmdline"] or []
            if config in cmdline and "daemon" in cmdline:
                process.send_signal(signal.SIGKILL)
        expect(term.get_by_text("disconnected")).to_be_visible(timeout=15)
        expect(term.get_by_text("working")).to_be_visible()
        expect(term.get_by_text("1 at a time")).to_be_visible()
        for key in ("+", "d"):
            term.write(key)
            time.sleep(0.5)
        expect(term.get_by_text("disconnected")).to_be_visible()
        tui.check(term)
    finally:
        release.touch()
    tui.signal(term, signal.SIGKILL)
