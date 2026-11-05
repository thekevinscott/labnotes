import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main
from labnotes.tui.run_output import RunOutput

INTERLEAVE = """
import sys, time
for i in range(4):
    print(f"out {i}", flush=True)
    time.sleep(0.05)
    print(f"err {i}", file=sys.stderr, flush=True)
    time.sleep(0.05)
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def project(root: Path, command: str, continues: bool = False) -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "interleave.py", INTERLEAVE)
    write(
        root / "exp" / "experiment.toml",
        f"continues = {str(continues).lower()}\ncommand = {json.dumps(command)}\n",
    )
    return root


def labnotes(root: Path, *argv: str) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), "experiments", "exp", "run", *argv])
    return exit_info.value.code


def only_run(root: Path) -> tuple[Path, dict[str, Any]]:
    [record] = (root / "exp" / "runs").glob("**/run.json")
    return record.parent, json.loads(record.read_text(encoding="utf-8"))


def shown(folder: Path) -> list[str]:
    output = RunOutput()
    output.follow(folder)
    return list(output.lines)


ORDER = [line for i in range(4) for line in (f"out {i}", f"err {i}")]


def test_shows_stdout_and_stderr_in_the_order_the_command_wrote_them(
    tmp_path: Path,
) -> None:
    root = project(tmp_path, f"{sys.executable} interleave.py")

    assert labnotes(root) == 0

    folder, run = only_run(root)
    assert shown(folder) == ORDER
    assert run["output"] == "output.jsonl"
    assert (folder / "stdout.log").read_text() == "out 0\nout 1\nout 2\nout 3\n"
    assert (folder / "stderr.log").read_text() == "err 0\nerr 1\nerr 2\nerr 3\n"


def test_orders_each_invocation_of_a_run_that_continues(tmp_path: Path) -> None:
    root = project(tmp_path, f"{sys.executable} interleave.py", continues=True)

    assert labnotes(root) == 0

    folder, run = only_run(root)
    [invocation] = run["invocations"]
    assert invocation["output"] == run["output"]
    assert (folder / invocation["output"]).exists()
    assert shown(folder) == ORDER


def test_copies_large_output_whole(tmp_path: Path) -> None:
    size = 5_000_000
    script = f"import sys; sys.stdout.write('x' * {size}); sys.stderr.write('done')"
    write(tmp_path / "big.py", script)
    root = project(tmp_path, f"{sys.executable} big.py")

    assert labnotes(root) == 0

    folder, _ = only_run(root)
    assert (folder / "stdout.log").stat().st_size == size
    entries = [json.loads(line) for line in (folder / "output.jsonl").open()]
    assert max(e["end"] for e in entries if e["stream"] == "stdout") == size
    assert [e for e in entries if e["stream"] == "stderr"][-1]["end"] == 4


def test_ends_the_run_when_a_leftover_helper_holds_the_output_open(
    tmp_path: Path,
) -> None:
    root = project(tmp_path, "sleep 20 & echo started")

    began = time.monotonic()
    assert labnotes(root) == 0

    assert time.monotonic() - began < 15
    folder, run = only_run(root)
    assert run["exit_code"] == 0
    assert shown(folder) == ["started"]


def test_keeps_the_output_of_a_run_stopped_by_its_timeout(tmp_path: Path) -> None:
    script = "import time; print('before', flush=True); time.sleep(30)"
    write(tmp_path / "slow.py", script)
    root = project(tmp_path, f"{sys.executable} slow.py")

    assert labnotes(root, "--timeout", "1") == 0

    folder, run = only_run(root)
    assert run["ended_by"] == "timeout"
    assert shown(folder) == ["before"]
