import os
import subprocess
import time
from pathlib import Path


def test_uvx_run_reads_code_captured_before_live_edit(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".gitignore").write_text("data/\nruns/\n")
    (root / "data").mkdir()
    (root / ".labnotes.toml").write_text('[runs]\npath = "runs/{experiment}/{run}"\n')
    (root / "exp").mkdir()
    (root / "exp/experiment.toml").write_text('command = "python cell.py {run_dir}"\n')
    (root / "value.py").write_text('VALUE = "before"\n')
    (root / "cell.py").write_text(
        "import pathlib, sys, time\n"
        'pathlib.Path("data/ready").touch()\n'
        'while not pathlib.Path("data/go").exists(): time.sleep(.02)\n'
        "from value import VALUE\n"
        'pathlib.Path(sys.argv[1], "result.txt").write_text(VALUE)\n'
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
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        env={**os.environ, **uvx},
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
        [result] = list((root / "runs/exp").glob("*/result.txt"))
        assert result.read_text() == "before"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
