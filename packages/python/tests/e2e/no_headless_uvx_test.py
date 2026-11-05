import os
import subprocess
from pathlib import Path


def test_uvx_run_requires_a_terminal(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text("continues = false\ncommand = 'true'\n")
    result = subprocess.run(
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
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "requires a terminal" in result.stderr
    assert not list(root.glob("exp/runs/*/run.json"))
