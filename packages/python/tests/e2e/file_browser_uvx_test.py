from pathlib import Path

from curtaincall import expect

from conftest import Tui

WORKLOAD = """\
import sys, time
from pathlib import Path

out = Path(sys.argv[1])
(out / "model.pt").write_bytes(bytes(range(256)))
for step in range(600):
    with (out / "metrics.txt").open("a") as file:
        file.write(f"metric step {step}\\n")
    if step == 15:
        (out / "late-sample.txt").write_text("written later\\n")
    time.sleep(0.1)
"""


def test_uvx_file_browser_lists_and_tails_run_files(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "work.py").write_text(WORKLOAD)
    (root / "alpha/experiment.toml").write_text(
        'command = "python work.py {run_dir}"\ncontinues = false\n'
        '[views]\nfiles = "labnotes.tui.file_browser:FileBrowser"\n'
    )
    term = tui(root, "experiments", "alpha", "run", cols=140)
    expect(term.get_by_text("2 files")).to_be_visible(timeout=60)
    term.write("2")
    expect(term.get_by_text("metrics.txt")).to_be_visible(timeout=30)
    expect(term.get_by_text("model.pt")).to_be_visible()
    expect(term.get_by_text("late-sample.txt")).to_be_visible(timeout=30)

    term.write("\x1b[B")
    term.write("\r")
    expect(term.get_by_text("late-sample.txt")).to_be_visible()
    expect(term.get_by_text("written later")).to_be_visible(timeout=10)

    term.write("\x1b[B")
    term.write("\r")
    expect(term.get_by_text("metric step 30")).to_be_visible(timeout=30)
    expect(term.get_by_text("metric step 45")).to_be_visible(timeout=30)

    term.write("\x1b[B")
    term.write("\r")
    expect(term.get_by_text("model.pt is binary (256 bytes)")).to_be_visible(timeout=10)
    tui.stop(term)
