import os
import subprocess
from pathlib import Path

from curtaincall import expect


def _commit(root: Path) -> None:
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


def test_uvx_run_can_read_git_inside_snapshot_submodule(
    tmp_path: Path, uvx: dict[str, str], terminal
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    (source / "version.txt").write_text("v1\n")
    _commit(source)
    expected_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source)

    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(source),
            "dependency",
        ],
        cwd=root,
        check=True,
    )
    (root / ".gitignore").write_text("runs/\n")
    (root / ".labnotes.toml").write_text('[runs]\npath = "runs/{experiment}/{run}"\n')
    (root / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "python cell.py {run_dir}"\n'
    )
    (root / "cell.py").write_text(
        "import pathlib, subprocess, sys\n"
        "run = pathlib.Path(sys.argv[1])\n"
        '(run / "sha.txt").write_bytes(subprocess.check_output(["git", "-C", "dependency", "rev-parse", "HEAD"]))\n'
        '(run / "status.txt").write_bytes(subprocess.check_output(["git", "-C", "dependency", "status", "--porcelain"]))\n'
    )
    _commit(root)
    (root / "dependency/version.txt").write_text("dirty\n")

    command = f"uvx labnotes -c {root / '.labnotes.toml'} experiments exp run"
    term = terminal(command, env={**os.environ, **uvx}, rows=30, cols=120)
    expect(term.get_by_text("1 passed, 0 failed")).to_be_visible(timeout=30)
    term.key_ctrl_c()
    term.wait()
    [run] = list((root / "runs/exp").iterdir())
    assert (run / "sha.txt").read_bytes() == expected_sha
    assert b" M version.txt" in (run / "status.txt").read_bytes()
    patch = (run / "git-diff.patch").read_bytes()
    assert b"diff --git a/dependency/version.txt b/dependency/version.txt" in patch
    assert b"+dirty" in patch
