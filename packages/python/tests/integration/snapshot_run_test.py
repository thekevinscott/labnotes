import os
import json
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from labnotes.runner.project_snapshot import project_snapshot


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
        f'continues = false\ncommand = "{sys.executable} cell.py {{run_dir}}"\n'
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
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} cell.py"\n'
    )
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
        f"continues = false\ncommand = \"{sys.executable} -c 'import os; print(os.getcwd())'\"\n"
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


def _fixture_repo(tmp_path: Path, cell: str) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".gitignore").write_text("runs/\n.venv/\n")
    (root / ".labnotes.toml").write_text('[runs]\npath = "runs/{experiment}/{run}"\n')
    (root / "exp").mkdir()
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} cell.py {{run_dir}}"\n'
    )
    (root / "cell.py").write_text(cell)
    return root


def _commit(root: Path) -> None:
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


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
        timeout=30,
    )


def test_ignored_venv_is_not_linked_to_live_project(tmp_path: Path) -> None:
    root = _fixture_repo(
        tmp_path,
        'import pathlib\npathlib.Path(".venv/marker").write_text("snapshot")\n',
    )
    venv = root / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (venv / ".gitignore").write_text("*\n")
    _commit(root)
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (venv / "marker").exists()


def test_snapshot_git_metadata_matches_live_repo_without_mutating_index(
    tmp_path: Path,
) -> None:
    root = _fixture_repo(
        tmp_path,
        "import pathlib, subprocess, sys\nrun = pathlib.Path(sys.argv[1])\nfor name, args in [('head', ['rev-parse', 'HEAD']), ('tag', ['describe', '--tags']), ('status', ['status', '--porcelain'])]:\n    (run / name).write_bytes(subprocess.check_output(['git', *args]))\n",
    )
    (root / "dirty.txt").write_text("original\n")
    _commit(root)
    subprocess.run(["git", "tag", "v1.2.3"], cwd=root, check=True)
    (root / "dirty.txt").write_text("changed\n")
    before_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
    before_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root)
    index_mtime = (root / ".git/index").stat().st_mtime_ns
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    [run] = list((root / "runs/exp").iterdir())
    assert (run / "head").read_bytes() == before_sha
    assert (run / "tag").read_text().strip() == "v1.2.3"
    assert (run / "status").read_bytes() == before_status
    assert (root / ".git/index").stat().st_mtime_ns == index_mtime
    assert (
        subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
        == before_status
    )


def test_dangling_tracked_symlink_survives_snapshot(tmp_path: Path) -> None:
    root = _fixture_repo(
        tmp_path,
        "import pathlib, sys\nlink = pathlib.Path('missing-link')\npathlib.Path(sys.argv[1], 'link-result').write_text(str(link.is_symlink()) + ':' + link.readlink().as_posix())\n",
    )
    (root / "missing-link").symlink_to("missing-target")
    _commit(root)
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    [run] = list((root / "runs/exp").iterdir())
    assert (run / "link-result").read_text() == "True:missing-target"


def test_snapshot_uses_default_temp_directory(tmp_path: Path) -> None:
    root = _fixture_repo(
        tmp_path,
        "import os, pathlib, sys\npathlib.Path(sys.argv[1], 'snapshot-path').write_text(os.getcwd())\n",
    )
    _commit(root)
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    [run] = list((root / "runs/exp").iterdir())
    snapshot = Path((run / "snapshot-path").read_text())
    assert snapshot.parent == Path(tempfile.gettempdir())
    assert snapshot.name.startswith("labnotes-")


def test_subfolder_snapshot_keeps_repo_layout_and_git_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project = repo / "sub"
    project.mkdir(parents=True)
    (repo / "sibling.txt").write_text("sibling\n")
    (project / ".labnotes.toml").write_text("")
    (project / "tracked.txt").write_text("original\n")
    _commit(repo)
    (repo / "sibling.txt").write_text("changed sibling\n")
    (project / "tracked.txt").write_text("changed\n")
    (project / "untracked.txt").write_text("untracked\n")
    expected = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo)
    expected_diff = subprocess.check_output(["git", "diff", "HEAD"], cwd=repo)

    with project_snapshot(project) as snapshot:
        assert snapshot.root.name == "sub"
        assert (snapshot.root.parent / "sibling.txt").read_text() == "changed sibling\n"
        assert snapshot.diff is not None
        assert snapshot.diff.startswith(expected_diff)
        assert snapshot.diff[len(expected_diff) :].endswith(
            b"+++ b/sub/untracked.txt\n@@ -0,0 +1 @@\n+untracked\n"
        )
        assert (snapshot.root / "tracked.txt").read_text() == "changed\n"
        assert (snapshot.root / "untracked.txt").read_text() == "untracked\n"
        assert (
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=snapshot.root.parent
            )
            == expected
        )
