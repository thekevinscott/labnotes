import json
import os
import subprocess
from pathlib import Path

import pytest


def damaged_project(tmp_path: Path, contents: str) -> Path:
    root = tmp_path / "project"
    run_file = root / "exp/runs/broken/run.json"
    run_file.parent.mkdir(parents=True)
    run_file.write_text(contents, encoding="utf-8")
    (root / ".labnotes.toml").write_text("", encoding="utf-8")
    (root / "exp/experiment.toml").write_text("", encoding="utf-8")
    return root


@pytest.mark.parametrize("contents", ["{not json", ""])
def test_uvx_lists_a_damaged_run_record(
    tmp_path: Path, uvx: dict[str, str], contents: str
) -> None:
    root = damaged_project(tmp_path, contents)
    result = subprocess.run(
        ["uvx", "labnotes", "experiments", "exp", "runs", "--format", "json"],
        cwd=root,
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    [run] = json.loads(result.stdout)
    assert run["id"] == "broken"
    assert run["folder"] == "exp/runs/broken"
    assert "run.json" in run["error"]
