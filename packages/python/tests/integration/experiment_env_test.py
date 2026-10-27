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
keys = ("BASE", "BOTH", "OWN", "DIR", "RID", "INV")
record = {"stage": stage, **{key: os.environ[key] for key in keys}}
record["daemon"] = next(
    parent.pid
    for parent in psutil.Process().parents()
    if parent.cmdline()[-2:] == ["labnotes", "daemon"]
    or parent.cmdline()[-1:] == ["daemon"]
)
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
        'DIR = "{run_dir}"\nRID = "{run_id}"\nINV = "{invocation_id}"\n',
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
    assert len({row["daemon"] for row in rows}) == 1
    for invocation in (rows[:4], rows[4:]):
        assert len({row["DIR"] for row in invocation}) == 1
        assert len({row["RID"] for row in invocation}) == 1
        assert len({row["INV"] for row in invocation}) == 1
        assert invocation[0]["RID"] == invocation[0]["INV"]
        assert Path(invocation[0]["DIR"]).is_absolute()
