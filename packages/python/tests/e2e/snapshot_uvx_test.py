import os
import shlex
import subprocess
import time
from pathlib import Path

from curtaincall import Terminal, expect


def test_uvx_run_reads_code_captured_before_live_edit(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
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
    term = Terminal(
        shlex.join(
            [
                "uvx",
                "labnotes",
                "-c",
                str(root / ".labnotes.toml"),
                "experiments",
                "exp",
                "run",
            ]
        ),
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )
    term.start()
    try:
        for _ in range(300):
            if (root / "data/ready").exists():
                break
            time.sleep(0.05)
        assert (root / "data/ready").exists(), term._get_screen_text()
        (root / "value.py").write_text('VALUE = "after"\n')
        (root / "data/go").touch()
        expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=20)
        term.key_ctrl_c()
        assert term.wait(timeout=10) == 0
        [result] = list((root / "runs/exp").glob("*/result.txt"))
        assert result.read_text() == "before"
    finally:
        term.kill()
