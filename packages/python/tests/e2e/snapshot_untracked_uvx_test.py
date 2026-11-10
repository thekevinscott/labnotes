import json
import subprocess
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_records_untracked_files_it_ran_with(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".gitignore").write_text("runs/\nsecret.txt\n")
    (root / ".labnotes.toml").write_text('[runs]\npath = "runs/{experiment}/{run}"\n')
    (root / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "python helper.py"\n'
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
    (root / "helper.py").write_text("print('helper ran')\n")
    (root / "secret.txt").write_text("hunter2\n")

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("helper ran")).to_be_visible()
    tui.quit(term)
    [run] = list((root / "runs/exp").iterdir())
    assert json.loads((run / "run.json").read_text())["git"]["dirty"] is True
    patch = (run / "git-diff.patch").read_text()
    assert "+++ b/helper.py\n@@ -0,0 +1 @@\n+print('helper ran')\n" in patch
    assert "secret" not in patch
