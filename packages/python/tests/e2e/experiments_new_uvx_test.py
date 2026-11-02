import os
import subprocess
import sys
import tomllib
from pathlib import Path


def labnotes(root: Path, uvx: dict[str, str], *argv: str) -> str:
    result = subprocess.run(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "experiments", *argv],
        cwd=root,
        env={**os.environ, **uvx},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout
    return result.stdout


def test_uvx_new_experiments_from_flags_and_from_another(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".labnotes.toml").write_text("")
    command = f"{sys.executable} -c 'pass' {{run_dir}}"

    labnotes(
        root,
        uvx,
        *["new", "sanity-3", "--command", command, "--repeats", "2"],
        *["--param", "model=opus", "--param", "model=sonnet"],
    )
    assert labnotes(root, uvx, "sanity-3", "run").endswith("4 passed, 0 failed.\n")
    labnotes(
        root, uvx, "new", "sanity-4", "--from", "sanity-3", "--param", "model=haiku"
    )

    copy = tomllib.loads((root / "sanity-4/experiment.toml").read_text())
    assert copy["from"] == "sanity-3"
    assert copy["command"] == command
    assert copy["params"] == {"model": ["haiku"]}
    assert not (root / "sanity-4/runs").exists()
    assert labnotes(root, uvx, "sanity-4", "run").endswith("2 passed, 0 failed.\n")
