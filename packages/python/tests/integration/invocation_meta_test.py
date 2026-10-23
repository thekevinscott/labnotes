import asyncio
import json
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import write

from labnotes.cli import main
from labnotes.read_config import read_config
from labnotes.tables.open_tables import open_tables

# Counts its own launches, so a test can see it ran once.
META = """
import json
import os
from pathlib import Path

calls = Path("calls.txt")
calls.write_text(calls.read_text() + "x" if calls.exists() else "x")
print(json.dumps({"commit": "abc", "cwd": os.getcwd()}))
"""

FAIL = """
import sys

sys.stderr.write("not a git repo")
sys.exit(2)
"""


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


def make_project(root: Path, script: str) -> Path:
    write(root / "meta.py", script)
    meta = shlex.join([sys.executable, "meta.py"])
    write(
        root / ".labnotes.toml",
        f'[experiments]\npath = "{{experiment}}"\n'
        f"[experiment]\nmeta = {json.dumps(meta)}\n",
    )
    write(
        root / "exp" / "experiment.toml",
        f'command = "{sys.executable} -c pass"\n[params]\nm = ["a", "b"]\n',
    )
    return root


def recorded(root: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "exp" / "runs").glob("**/run.json"))
    ]


def commits(root: Path) -> list[object]:
    async def go() -> list[object]:
        tables = open_tables(read_config(root / ".labnotes.toml"))
        rows = await tables.query("SELECT meta ->> 'commit' AS sha FROM runs")
        return [row["sha"] for row in rows]

    return asyncio.run(go())


def test_records_the_meta_from_one_call_in_every_run(tmp_path: Path) -> None:
    root = make_project(tmp_path, META)

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    meta = {"commit": "abc", "cwd": str(root)}
    assert [run["meta"] for run in recorded(root)] == [meta, meta]
    assert (root / "calls.txt").read_text() == "x"
    assert commits(root) == ["abc", "abc"]


def test_fails_before_any_run_when_the_meta_command_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, FAIL)

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    err = capsys.readouterr().err
    assert "meta.py exited 2: not a git repo" in err
    assert not (root / "exp" / "runs").exists()
