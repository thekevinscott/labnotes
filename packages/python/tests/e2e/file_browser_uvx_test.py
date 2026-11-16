from pathlib import Path

from curtaincall import expect

from conftest import Tui

WRITER = """
import sys
import time
from pathlib import Path

folder = Path(sys.argv[1])
(folder / "plot.png").write_bytes(b"\\x89PNG\\r\\n\\x1a\\n\\x00" + bytes(range(256)))
release = Path(sys.argv[2])
with (folder / "a-progress.log").open("w", buffering=1) as log:
    log.write("step 1\\n")
    while not release.exists():
        time.sleep(0.1)
    log.write("step 2 after release\\n")
    time.sleep(30)
"""


def test_installed_tui_browses_the_open_runs_files_and_tails_one(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "writer.py").write_text(WRITER)
    release = root / "release"
    (root / "alpha/experiment.toml").write_text(
        f'command = "python {root / "writer.py"} {{run_dir}} {release}"\n'
        "continues = false\n"
        '[views]\nfiles = "labnotes.tui.file_browser:FileBrowser"\n'
    )
    term = tui(root, "experiments", "alpha", "run", rows=40, cols=160)
    expect(term.get_by_text("2 files")).to_be_visible(timeout=60)
    term.write("2")
    expect(term.get_by_text("a-progress.log")).to_be_visible(timeout=30)
    expect(term.get_by_text("plot.png")).to_be_visible(timeout=30)
    term.key_enter()
    expect(term.get_by_text("step 1")).to_be_visible(timeout=30)
    release.write_text("")
    expect(term.get_by_text("step 2 after release")).to_be_visible(timeout=30)
    tui.stop(term)
