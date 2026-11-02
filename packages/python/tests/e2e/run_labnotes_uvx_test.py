import json
import os
import shlex
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path


def test_uvx_run_records_the_labnotes_version_and_command_line(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} -c pass"\n[params]\nm = ["a", "b"]\n'
    )
    argv = ["-c", str(root / ".labnotes.toml"), "experiments", "exp", "run"]
    argv += ["--m=b", "--", "--auth", "api key"]

    result = subprocess.run(
        ["uvx", "labnotes", *argv],
        cwd=root,
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    [record] = root.glob("exp/runs/**/run.json")
    run = json.loads(record.read_text())
    assert run["labnotes_version"] == version("labnotes")
    assert run["labnotes_command"] == shlex.join(["labnotes", *argv])
