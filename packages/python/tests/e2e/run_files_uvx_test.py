import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

WRITER = """
import sys
import time
from pathlib import Path

folder, release = Path(sys.argv[1]), Path(sys.argv[2])
(folder / "b-plot.png").write_bytes(b"\\x89PNG\\r\\n\\x1a\\n\\x00" + bytes(range(256)))
with (folder / "a-progress.log").open("w", buffering=1) as log:
    log.write("step 1\\n")
    while not release.exists():
        time.sleep(0.1)
    (folder / "c-late.txt").write_text("late\\n")
    log.write("step 2 after release\\n")
    time.sleep(60)
"""


def test_an_open_run_browses_its_files_and_tails_one(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "writer.py").write_text(WRITER)
    release = tmp_path / "release"
    (root / "alpha/experiment.toml").write_text(
        f'command = "{sys.executable} {root / "writer.py"} {{run_dir}} {release}"\n'
        "continues = false\n"
    )

    term = tui(root, "experiments", "alpha", "run", rows=30, cols=160)

    expect(term.get_by_text("stdout (0)")).to_be_visible(timeout=60)
    expect(term.get_by_text("files (")).to_be_visible()
    term.write("t")
    term.write("t")
    expect(term.get_by_text("a-progress.log")).to_be_visible(timeout=30)
    expect(term.get_by_text("b-plot.png")).to_be_visible()
    expect(term.get_by_text("c-late.txt")).not_to_be_visible()
    term.key_enter()
    expect(term.get_by_text("step 1")).to_be_visible(timeout=30)
    release.write_text("")
    expect(term.get_by_text("step 2 after release")).to_be_visible(timeout=30)
    expect(term.get_by_text("c-late.txt")).to_be_visible(timeout=30)
    term.key_down()
    term.key_enter()
    expect(term.get_by_text("b-plot.png is binary")).to_be_visible(timeout=30)
    expect(term.get_by_text("step 2 after release")).not_to_be_visible()
    tui.stop(term)
