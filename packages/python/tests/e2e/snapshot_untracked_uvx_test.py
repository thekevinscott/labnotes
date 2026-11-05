from conftest import run_uvx_tui
import json
import subprocess
from pathlib import Path


def test_uvx_run_records_untracked_files_it_ran_with(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
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
    (root / "helper.py").write_text("print('helper')\n")
    (root / "secret.txt").write_text("hunter2\n")
    result = run_uvx_tui(root, uvx, "experiments", "exp", "run")
    assert result.returncode == 0, result.stdout + result.stderr
    [run] = list((root / "runs/exp").iterdir())
    assert json.loads((run / "run.json").read_text())["git"]["dirty"] is True
    patch = (run / "git-diff.patch").read_text()
    assert "+++ b/helper.py\n@@ -0,0 +1 @@\n+print('helper')\n" in patch
    assert "secret" not in patch
