from conftest import run_uvx_tui
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

MANY = '[params]\nm = ["a", "b"]\n'
CAPTURE = (
    "import json, os, sys\n"
    'with open("journal.jsonl", "a") as journal:\n'
    '    journal.write(json.dumps([sys.argv[1], os.environ.get("LABEL")]) + "\\n")\n'
)
SET_STATE = "from labnotes import set_state\nset_state({'resource': 'up'})\n"
GET_STATE = (
    "import json, sys\nfrom labnotes import get_state\n"
    'with open("journal.jsonl", "a") as journal:\n'
    '    journal.write(json.dumps([sys.argv[1], get_state()]) + "\\n")\n'
)


def project(root: Path, experiment: str, env: str = "") -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(
        f'[experiments]\npath = "{{experiment}}"\n{env}'
    )
    (root / "exp/experiment.toml").write_text(experiment)
    return root


def labnotes(root: Path, uvx: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "LABEL"}
    return run_uvx_tui(root, uvx, "experiments", "exp", "run", env=env)


def journal(root: Path) -> list[object]:
    lines = (root / "journal.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def test_uvx_run_refuses_invocation_dir_in_setup_before_setup_runs(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(
        tmp_path / "project",
        'continues = false\ncommand = "echo run >> journal.txt"\n'
        'setup = "echo up {invocation_dir} >> journal.txt"\n',
    )

    result = labnotes(root, uvx)

    assert result.returncode != 0, result.stdout + result.stderr
    assert (
        "setup command echo up {invocation_dir} >> journal.txt uses "
        "{invocation_dir}; setup, teardown, and meta get no folder placeholders. "
        "Share values with set_state() and get_state()."
    ) in result.stderr
    assert not (root / "journal.txt").exists()


def test_uvx_matrix_run_gives_invocation_dir_env_to_runs_but_not_setup(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(
        tmp_path / "project",
        f'continues = false\ncommand = "{sys.executable} capture.py run"\n'
        f'setup = "{sys.executable} capture.py setup"\n' + MANY,
        '[experiment.env]\nLABEL = "{invocation_dir}"\n',
    )
    (root / "capture.py").write_text(CAPTURE)

    result = labnotes(root, uvx)

    assert result.returncode == 0, result.stdout + result.stderr
    folders = sorted(str(p.resolve()) for p in (root / "exp/runs").iterdir())
    rows = journal(root)
    assert rows[0] == ["setup", None]
    assert sorted(rows[1:]) == [["run", folder] for folder in folders]


@pytest.mark.parametrize("params", ["", MANY])
def test_uvx_setup_state_reaches_runs_and_teardown(
    tmp_path: Path, uvx: dict[str, str], params: str
) -> None:
    root = project(
        tmp_path / "project",
        f'continues = false\ncommand = "{sys.executable} get.py run"\n'
        f'setup = "{sys.executable} set.py"\n'
        f'teardown = "{sys.executable} get.py teardown"\n' + params,
    )
    (root / "set.py").write_text(SET_STATE)
    (root / "get.py").write_text(GET_STATE)

    result = labnotes(root, uvx)

    assert result.returncode == 0, result.stdout + result.stderr
    runs = 2 if params else 1
    state = {"resource": "up"}
    assert journal(root) == [["run", state]] * runs + [["teardown", state]]
