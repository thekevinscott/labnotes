import os
import subprocess
from pathlib import Path


def test_uvx_run_rejects_an_escaping_runs_path_before_writing(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(
        '[runs]\npath = "../escaped-{experiment}/{run}"\n'
    )
    (root / "alpha/experiment.toml").write_text(
        'command = "python3 -c pass"\ncontinues = false\n'
    )

    result = subprocess.run(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "alpha",
            "run",
            "--headless",
        ],
        cwd=root,
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "[runs] path must be relative" in result.stderr
    assert not (tmp_path / "escaped-alpha").exists()
