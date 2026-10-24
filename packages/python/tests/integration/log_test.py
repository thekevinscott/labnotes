import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main

SCRIPT = """
from labnotes import log

log({"content": "answer"})
log({"id": "t1", "phase": "start", "type": "thinking"})
"""


def test_loads_only_the_standard_library() -> None:
    code = (
        "import sys\n"
        "before = set(sys.modules)\n"
        "from labnotes import log\n"
        "print(callable(log))\n"
        "print('\\n'.join(sorted(set(sys.modules) - before)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    is_callable, *loaded = result.stdout.split()
    tops = {name.split(".")[0] for name in loaded}

    assert is_callable == "True"
    assert {name for name in loaded if name.startswith("labnotes")} == {
        "labnotes",
        "labnotes.log",
        "labnotes.log_path",
        "labnotes.view",
        "labnotes.view.answer",
        "labnotes.view.build",
        "labnotes.view.respond",
        "labnotes.view.serve",
    }
    assert tops - set(sys.stdlib_module_names) == {"labnotes"}


@pytest.fixture
def outer_log(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "outer.jsonl"
    with mock.patch.dict(os.environ, {"LABNOTES_LOG": str(path)}):
        yield path


def test_a_run_logs_to_its_own_folder(tmp_path: Path, outer_log: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "script.py").write_text(SCRIPT)
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp" / "experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
    )

    with pytest.raises(SystemExit):
        main(["-c", str(tmp_path / ".labnotes.toml"), "experiments", "exp", "run"])

    [path] = (tmp_path / "exp" / "runs").glob("**/log.jsonl")
    blocks = [json.loads(line) for line in path.read_text().splitlines()]
    assert [{k: v for k, v in b.items() if k != "timestamp"} for b in blocks] == [
        {"content": "answer"},
        {"id": "t1", "phase": "start", "type": "thinking"},
    ]
    assert all("timestamp" in block for block in blocks)
    assert (path.parent / "stdout.log").read_text() == ""
    assert not outer_log.exists()
