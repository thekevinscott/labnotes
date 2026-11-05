import json
import os
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from conftest import write

from conftest import run_tui_command


CAPTURE = """
import json
import os
import sys
from pathlib import Path
import psutil

stage = sys.argv[1]
keys = ("BASE", "BOTH", "OWN", "INV_DIR")
record = {"stage": stage, **{key: os.environ.get(key) for key in keys}}
with Path("journal.jsonl").open("a") as journal:
    journal.write(json.dumps(record) + "\\n")
if stage == "meta":
    print(json.dumps({"caller": os.environ["BOTH"]}))
"""


@pytest.fixture
def caller_environment() -> Iterator[dict[str, str]]:
    with mock.patch.dict(os.environ, {"BOTH": "first"}):
        yield os.environ


def test_configured_environment_reaches_every_stage_from_each_cli_invocation(
    tmp_path: Path, caller_environment: dict[str, str]
) -> None:
    write(tmp_path / "capture.py", CAPTURE)
    write(
        tmp_path / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n[experiment.env]\n'
        'BASE = "base"\nBOTH = "base"\n',
    )
    command = shlex.join([sys.executable, "capture.py"])
    write(
        tmp_path / "exp" / "experiment.toml",
        f'continues = false\ncommand = "{command} run"\n'
        'counts = "false"\n'
        f'meta = "{command} meta"\n'
        f'setup = "{command} setup"\n'
        f'teardown = "{command} teardown"\n'
        '[env]\nBOTH = "experiment"\nOWN = "own"\n'
        'INV_DIR = "{invocation_dir}"\n',
    )

    for caller in ("first", "second"):
        caller_environment["BOTH"] = caller
        assert run_tui_command(tmp_path, ["experiments", "exp", "run"]) == 0

    rows = [
        json.loads(line)
        for line in (tmp_path / "journal.jsonl").read_text().splitlines()
    ]
    assert [row["stage"] for row in rows] == ["meta", "setup", "run", "teardown"] * 2
    assert [row["BOTH"] for row in rows] == ["first"] * 4 + ["second"] * 4
    assert {row["BASE"] for row in rows} == {"base"}
    assert {row["OWN"] for row in rows} == {"own"}
    folders = sorted(str(p.resolve()) for p in (tmp_path / "exp" / "runs").iterdir())
    hooks = [row["INV_DIR"] for row in rows if row["stage"] != "run"]
    assert hooks == [None] * 6
    assert sorted(row["INV_DIR"] for row in rows if row["stage"] == "run") == folders


LABEL_CAPTURE = """
import json
import os
import sys
from pathlib import Path

record = [sys.argv[1], os.environ.get("LABEL")]
with Path("journal.jsonl").open("a") as journal:
    journal.write(json.dumps(record) + "\\n")
"""


@pytest.fixture
def without_label() -> Iterator[None]:
    unset = {key: value for key, value in os.environ.items() if key != "LABEL"}
    with mock.patch.dict(os.environ, unset, clear=True):
        yield


MANY = '[params]\nm = ["a", "b"]\n'


@pytest.mark.usefixtures("without_label")
@pytest.mark.parametrize("params", ["", MANY])
@pytest.mark.parametrize("placeholder", ["{run_dir}", "{invocation_dir}"])
def test_folder_env_values_are_left_out_of_hooks_and_given_to_the_runs(
    tmp_path: Path, params: str, placeholder: str
) -> None:
    write(tmp_path / "capture.py", LABEL_CAPTURE)
    write(
        tmp_path / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n'
        f'[experiment.env]\nLABEL = "{placeholder}"\n',
    )
    command = shlex.join([sys.executable, "capture.py"])
    write(
        tmp_path / "exp" / "experiment.toml",
        f'continues = false\ncommand = "{command} run"\n'
        f'meta = "{command} meta && echo {{}}"\n'
        f'setup = "{command} setup"\n'
        f'teardown = "{command} teardown"\n' + params,
    )

    assert run_tui_command(tmp_path, ["experiments", "exp", "run"]) == 0
    runs = tmp_path / "exp" / "runs"
    folders = sorted(path.parent.resolve() for path in runs.rglob("run.json"))
    rows = [
        json.loads(line)
        for line in (tmp_path / "journal.jsonl").read_text().splitlines()
    ]
    assert rows[:2] + rows[-1:] == [["meta", None], ["setup", None], ["teardown", None]]
    assert sorted(row[1] for row in rows[2:-1]) == [str(f) for f in folders]
