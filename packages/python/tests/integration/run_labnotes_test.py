import json
import shlex
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main


def make_project(root: Path) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp" / "experiment.toml").write_text(
        f'command = "{sys.executable} -c pass"\n[params]\nm = ["a", "b"]\n'
    )
    return root


def labnotes(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 0


def only_run(root: Path) -> dict[str, Any]:
    [path] = (root / "exp" / "runs").glob("**/run.json")
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return record


def test_records_the_labnotes_version_and_command_line(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    argv = ["-c", str(root / ".labnotes.toml"), "experiments", "exp", "run"]
    argv += ["--m=a", "--timeout", "60", "--", "--auth", "api key"]

    labnotes(argv)

    run = only_run(root)
    assert run["labnotes_version"] == version("labnotes")
    assert run["labnotes_command"] == shlex.join(["labnotes", *argv])
