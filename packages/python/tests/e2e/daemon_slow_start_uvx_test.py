import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from conftest import run_uvx_tui


def test_installed_run_waits_for_slow_snapshot_preparation(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\ncommand = 'true'\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "add", ".labnotes.toml", "exp/experiment.toml"],
        cwd=tmp_path,
        check=True,
    )
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
        cwd=tmp_path,
        check=True,
    )

    real_git = shutil.which("git")
    assert real_git is not None
    bin_dir = tmp_path / "git-wrapper"
    bin_dir.mkdir()
    marker = tmp_path / "clone-delayed"
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "clone" ]; then\n'
        f"  touch {shlex.quote(str(marker))}\n"
        "  sleep 11\n"
        "fi\n"
        f'exec {shlex.quote(real_git)} "$@"\n'
    )
    wrapper.chmod(0o755)

    result = run_uvx_tui(
        tmp_path,
        uvx,
        "experiments",
        "exp",
        "run",
        timeout=45,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )

    assert marker.exists(), "Git snapshot preparation was not delayed"
    assert result.returncode == 0, result.stdout
    assert "1 passed, 0 failed" in result.stdout
    runs = list(tmp_path.glob("exp/runs/*/run.json"))
    assert len(runs) == 1
    assert json.loads(runs[0].read_text())["exit_code"] == 0
