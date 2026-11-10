import subprocess
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_reads_code_captured_before_live_edit(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".gitignore").write_text("data/\nruns/\n")
    (root / "data").mkdir()
    (root / ".labnotes.toml").write_text('[runs]\npath = "runs/{experiment}/{run}"\n')
    (root / "exp").mkdir()
    (root / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "python cell.py {run_dir}"\n'
    )
    (root / "value.py").write_text('VALUE = "before"\n')
    (root / "cell.py").write_text(
        "import pathlib, sys, time\n"
        'print("waiting for go", flush=True)\n'
        'while not pathlib.Path("data/go").exists(): time.sleep(.02)\n'
        "from value import VALUE\n"
        'pathlib.Path(sys.argv[1], "result.txt").write_text(VALUE)\n'
        'print("value is", VALUE)\n'
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "initial",
        ],
        cwd=root,
        check=True,
    )
    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("waiting for go")).to_be_visible(timeout=120)

    (root / "value.py").write_text('VALUE = "after"\n')
    (root / "data/go").touch()

    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=20)
    expect(term.get_by_text("value is before")).to_be_visible()
    tui.quit(term)
    [result] = list((root / "runs/exp").glob("*/result.txt"))
    assert result.read_text() == "before"
