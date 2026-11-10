import os
import subprocess
import sys
import tomllib
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def new(root: Path, uvx: dict[str, str], *argv: str) -> None:
    result = subprocess.run(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "experiments", "new"]
        + list(argv),
        cwd=root,
        env={**os.environ, **uvx},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout


def run(tui: Tui, root: Path, experiment: str, summary: str) -> None:
    term = tui(root, "experiments", experiment, "run")
    expect(term.get_by_text(summary)).to_be_visible(timeout=120)
    tui.quit(term)


def test_uvx_new_experiments_from_flags_and_from_another(
    tmp_path: Path, uvx: dict[str, str], tui: Tui
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".labnotes.toml").write_text("")
    command = f"{sys.executable} -c 'pass' {{run_dir}}"

    new(
        root,
        uvx,
        *["sanity-3", "--command", command, "--repeats", "2"],
        *["--param", "model=opus", "--param", "model=sonnet"],
    )
    run(tui, root, "sanity-3", "4 passed, 0 failed.")
    new(root, uvx, "sanity-4", "--from", "sanity-3", "--param", "model=haiku")

    copy = tomllib.loads((root / "sanity-4/experiment.toml").read_text())
    assert copy["from"] == "sanity-3"
    assert copy["command"] == command
    assert copy["params"] == {"model": ["haiku"]}
    assert not (root / "sanity-4/runs").exists()
    run(tui, root, "sanity-4", "2 passed, 0 failed.")
