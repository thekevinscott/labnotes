import asyncio
import json
import sys
from pathlib import Path

import pytest

from labnotes.cli import main
from labnotes.read_config import read_config
from labnotes.tables.open_tables import open_tables

# Holds 80 MB for a second, long enough for a few samples.
SCRIPT = """
import time

held = b"y" * 80_000_000
time.sleep(1.2)
"""


# Two children, one with a grandchild, each a fresh interpreter holding 60 MB,
# so no pages are shared and the tree's RSS sum is the true total.
TREE = """
import subprocess
import sys
import time

HOLD = "held = b'y' * 60_000_000; import time; time.sleep(2)"
NEST = f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {HOLD!r}]); {HOLD}"
children = [
    subprocess.Popen([sys.executable, "-c", HOLD]),
    subprocess.Popen([sys.executable, "-c", NEST]),
]
held = b"y" * 60_000_000
for child in children:
    child.wait()
time.sleep(0.5)
"""


def make_project(root: Path, settings: str, script: str = SCRIPT) -> Path:
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(script)
    (root / "exp").mkdir()
    (root / "exp" / "experiment.toml").write_text(
        f"command = '{sys.executable} script.py'\n{settings}"
    )
    return root


def run_once(root: Path) -> Path:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), "experiments", "exp", "run"])
    assert exit_info.value.code == 0
    [record] = root.glob("exp/runs/*/run.json")
    return record.parent


def query(root: Path, sql: str) -> list[dict[str, object]]:
    async def read() -> list[dict[str, object]]:
        return await open_tables(read_config(root / ".labnotes.toml")).query(sql)

    return asyncio.run(read())


def test_records_the_runs_memory_over_time(tmp_path: Path) -> None:
    root = make_project(tmp_path, "memory_interval = 0.2\n")

    folder = run_once(root)

    samples = [
        json.loads(line) for line in (folder / "memory.jsonl").read_text().splitlines()
    ]
    assert len(samples) >= 3
    assert all(sample["processes"] >= 1 for sample in samples)
    assert max(sample["rss"] for sample in samples) > 80_000_000
    times = [sample["time"] for sample in samples]
    assert times == sorted(times)
    rows = query(
        root, "SELECT run, line, time, rss, processes FROM memory ORDER BY line"
    )
    assert [row["rss"] for row in rows] == [sample["rss"] for sample in samples]
    assert {row["run"] for row in rows} == {folder.name}


def test_counts_every_process_the_run_starts(tmp_path: Path) -> None:
    root = make_project(tmp_path, "memory_interval = 0.2\n", TREE)

    folder = run_once(root)

    samples = [
        json.loads(line) for line in (folder / "memory.jsonl").read_text().splitlines()
    ]
    peak = max(samples, key=lambda sample: sample["rss"])
    assert max(sample["processes"] for sample in samples) >= 4
    # Four interpreters hold 240 MB between them; each adds tens of MB of its own.
    assert 240_000_000 < peak["rss"] < 480_000_000


def test_records_no_memory_with_the_interval_at_0(tmp_path: Path) -> None:
    root = make_project(tmp_path, "memory_interval = 0\n")

    folder = run_once(root)

    assert not (folder / "memory.jsonl").exists()
    assert query(root, "SELECT * FROM memory") == []
