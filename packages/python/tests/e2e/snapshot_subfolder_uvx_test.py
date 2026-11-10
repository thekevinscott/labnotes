import subprocess
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_from_repo_subfolder_uses_subfolder_snapshot(
    tmp_path: Path, tui: Tui
) -> None:
    repo = tmp_path / "repo"
    project = repo / "sub"
    (project / "exp").mkdir(parents=True)
    (repo / "sibling.txt").write_text("sibling\n")
    (project / ".gitignore").write_text("runs/\n")
    (project / ".labnotes.toml").write_text(
        '[runs]\npath = "runs/{experiment}/{run}"\n'
    )
    (project / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "python cell.py {run_dir}"\n'
    )
    (project / "cell.py").write_text(
        "import os, pathlib, subprocess, sys\n"
        "run = pathlib.Path(sys.argv[1])\n"
        '(run / "cwd.txt").write_text(os.getcwd())\n'
        '(run / "sibling.txt").write_text(pathlib.Path("../sibling.txt").read_text())\n'
        '(run / "status.txt").write_bytes(subprocess.check_output(["git", "status", "--porcelain"]))\n'
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
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
        cwd=repo,
        check=True,
    )
    (project / "dirty.txt").write_text("untracked\n")
    expected = subprocess.check_output(["git", "status", "--porcelain"], cwd=project)

    term = tui(project, "experiments", "exp", "run")

    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    tui.quit(term)
    [run] = list((project / "runs/exp").iterdir())
    snapshot_root = Path((run / "cwd.txt").read_text())
    assert snapshot_root != project
    assert snapshot_root.name == "sub"
    assert (run / "sibling.txt").read_text() == "sibling\n"
    assert (run / "status.txt").read_bytes() == expected
