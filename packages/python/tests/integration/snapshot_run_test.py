import os
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_running_cell_keeps_original_code_and_repo_outputs(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "data").mkdir()
    (root / ".gitignore").write_text("data/\nruns/\n.env\n")
    (root / ".env").write_text("secret")
    (root / "value.py").write_text('VALUE = "before"\n')
    (root / ".labnotes.toml").write_text('[runs]\npath = "runs/{experiment}/{run}"\n')
    (root / "exp").mkdir()
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} cell.py {{run_dir}}"\n'
        f'setup = "{sys.executable} hook.py setup"\n'
        f'teardown = "{sys.executable} hook.py teardown"\n'
    )
    (root / "hook.py").write_text(
        "import os, pathlib, sys\n"
        'pathlib.Path("data/hooks").open("a").write(sys.argv[1] + ":" + os.getcwd() + "\\n")\n'
    )
    (root / "cell.py").write_text(
        "import os, pathlib, sys, time\n"
        'pathlib.Path("data/ready").write_text(os.getcwd())\n'
        'while not pathlib.Path("data/go").exists(): time.sleep(.02)\n'
        "from value import VALUE\n"
        'pathlib.Path(sys.argv[1], "result.txt").write_text(VALUE + ":" + os.getcwd() + ":" + pathlib.Path(".env").read_text())\n'
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
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    (root / "value.py").write_text('VALUE = "dirty original"\n')
    diff = subprocess.check_output(["git", "diff", "HEAD"], cwd=root, text=True)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(300):
            if (root / "data/ready").exists():
                break
            if process.poll() is not None:
                break
            time.sleep(0.05)
        assert (root / "data/ready").exists(), process.communicate(timeout=2)[0]
        (root / "value.py").write_text('VALUE = "after"\n')
        (root / "data/go").touch()
        output, _ = process.communicate(timeout=20)
        assert process.returncode == 0, output
        [run] = list((root / "runs/exp").glob("*/result.txt"))
        snapshot = Path((root / "data/ready").read_text())
        assert snapshot != root
        assert run.read_text() == f"dirty original:{snapshot}:secret"
        assert (root / "data/hooks").read_text().splitlines() == [
            f"setup:{snapshot}",
            f"teardown:{snapshot}",
        ]
        assert (run.parent / "git-sha.txt").read_text().strip() == sha
        assert (run.parent / "git-diff.patch").read_text() == diff
        assert json.loads((run.parent / "run.json").read_text())["git"] == {
            "commit": sha,
            "dirty": True,
        }
        assert not snapshot.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_signal_removes_snapshot(tmp_path: Path, signum: signal.Signals) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".gitignore").write_text("data/\n")
    (root / "data").mkdir()
    (root / ".labnotes.toml").write_text("")
    (root / "exp").mkdir()
    (root / "exp/experiment.toml").write_text(f'command = "{sys.executable} cell.py"\n')
    (root / "cell.py").write_text(
        "import os, pathlib, time\n"
        'pathlib.Path("data/cwd").write_text(os.getcwd())\n'
        "time.sleep(600)\n"
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
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(300):
            if (root / "data/cwd").exists():
                break
            if process.poll() is not None:
                break
            time.sleep(0.05)
        assert (root / "data/cwd").exists(), process.communicate(timeout=2)[0]
        snapshot = Path((root / "data/cwd").read_text())
        process.send_signal(signum)
        process.communicate(timeout=20)
        assert not snapshot.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_non_git_project_uses_live_root_and_warns(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".labnotes.toml").write_text("")
    (root / "exp").mkdir()
    (root / "exp/experiment.toml").write_text(
        f"command = \"{sys.executable} -c 'import os; print(os.getcwd())'\"\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "not a git repository; running from the live tree" in result.stderr
    [stdout] = list((root / "exp/runs").glob("*/stdout.log"))
    assert stdout.read_text().strip() == str(root)
