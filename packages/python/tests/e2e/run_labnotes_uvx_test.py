from conftest import run_uvx_tui
import json
import shlex
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
        f'command = "{sys.executable} -c pass"\ncontinues = false\n[params]\nm = ["a", "b"]\n'
    )
    argv = ["-c", str(root / ".labnotes.toml"), "experiments", "exp", "run"]
    argv += ["--m=b", "--", "--auth", "api key"]

    result = run_uvx_tui(
        root, uvx, "experiments", "exp", "run", "--m=b", "--", "--auth", "api key"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    [record] = root.glob("exp/runs/**/run.json")
    run = json.loads(record.read_text())
    assert run["labnotes_version"] == version("labnotes")
    assert run["labnotes_command"] == shlex.join(["labnotes", *argv])
