import json
import os
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from conftest import write

from labnotes.cli import main


CAPTURE = """
import json
import os
import sys
from pathlib import Path
import psutil

stage = sys.argv[1]
keys = ("BASE", "BOTH", "OWN", "INV_DIR")
record = {"stage": stage, **{key: os.environ[key] for key in keys}}
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
        f'command = "{command} run"\n'
        f'meta = "{command} meta"\n'
        f'setup = "{command} setup"\n'
        f'teardown = "{command} teardown"\n'
        '[env]\nBOTH = "experiment"\nOWN = "own"\n'
        'INV_DIR = "{invocation_dir}"\n',
    )

    for caller in ("first", "second"):
        caller_environment["BOTH"] = caller
        with pytest.raises(SystemExit) as exit_info:
            main(["-c", str(tmp_path / ".labnotes.toml"), "experiments", "exp", "run"])
        assert exit_info.value.code == 0

    rows = [
        json.loads(line)
        for line in (tmp_path / "journal.jsonl").read_text().splitlines()
    ]
    assert [row["stage"] for row in rows] == ["meta", "setup", "run", "teardown"] * 2
    assert [row["BOTH"] for row in rows] == ["first"] * 4 + ["second"] * 4
    assert {row["BASE"] for row in rows} == {"base"}
    assert {row["OWN"] for row in rows} == {"own"}
    for invocation in (rows[:4], rows[4:]):
        assert len({row["INV_DIR"] for row in invocation}) == 1
        assert Path(invocation[0]["INV_DIR"]).is_absolute()


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


@pytest.mark.usefixtures("without_label")
def test_run_dir_env_value_is_left_out_of_hooks_and_given_to_the_run(
    tmp_path: Path,
) -> None:
    write(tmp_path / "capture.py", LABEL_CAPTURE)
    write(
        tmp_path / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n'
        '[experiment.env]\nLABEL = "{run_dir}"\n',
    )
    command = shlex.join([sys.executable, "capture.py"])
    write(
        tmp_path / "exp" / "experiment.toml",
        f'command = "{command} run"\nsetup = "{command} setup"\n',
    )

    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(tmp_path / ".labnotes.toml"), "experiments", "exp", "run"])

    assert exit_info.value.code == 0
    [folder] = (tmp_path / "exp" / "runs").iterdir()
    assert [
        json.loads(line)
        for line in (tmp_path / "journal.jsonl").read_text().splitlines()
    ] == [["setup", None], ["run", str(folder.resolve())]]
