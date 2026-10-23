import json
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main

# Writes 2 MB into its folder and holds 80 MB, then waits while hold exists.
SCRIPT = """
import sys
import time
from pathlib import Path

Path(sys.argv[1], "out.bin").write_bytes(b"x" * 2_000_000)
held = b"y" * 80_000_000
while Path("hold").exists():
    time.sleep(0.1)
"""
LABNOTES = Path(sys.executable).parent / "labnotes"


def make_project(root: Path) -> Path:
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "exp").mkdir()
    (root / "exp" / "experiment.toml").write_text(
        f"command = '{sys.executable} script.py {{run_dir}}'\n"
    )
    return root


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


def cli(root: Path, *argv: str) -> str:
    return subprocess.run(
        [LABNOTES, "-c", root / ".labnotes.toml", *argv],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout


def listed(root: Path) -> list[dict[str, Any]]:
    return json.loads(cli(root, "experiments", "exp", "runs", "--format", "json"))  # type: ignore[no-any-return]


def test_lists_a_finished_runs_size_and_no_memory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path)
    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    [run] = listed(root)
    recorded = json.loads((root / run["folder"] / "run.json").read_text())
    assert isinstance(recorded["pid"], int)
    assert run["memory"] is None
    assert 2_000_000 < run["size"] < 2_100_000


@pytest.fixture
def running(tmp_path: Path) -> Iterator[Path]:
    root = make_project(tmp_path)
    (root / "hold").touch()
    process = subprocess.Popen(
        [LABNOTES, "-c", root / ".labnotes.toml", "experiments", "exp", "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield root
    finally:
        (root / "hold").unlink()
        process.wait(timeout=30)


def wait_for[T](check: Any) -> T:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if (found := check()) is not None:
            return found  # type: ignore[no-any-return]
        time.sleep(0.2)
    raise AssertionError("timed out")


def test_reports_a_running_runs_memory_and_size(running: Path) -> None:
    def usage() -> dict[str, Any] | None:
        for line in cli(running, "run", "status", "--json").splitlines():
            event = json.loads(line)
            if event["event"] == "usage" and (event["memory"] or 0) > 80_000_000:
                return event  # type: ignore[no-any-return]
        return None

    event: dict[str, Any] = wait_for(usage)
    assert event["experiment"] == "exp"
    assert event["size"] > 2_000_000
    said = cli(running, "run", "status")
    assert " MB of memory, 2.0 MB on disk." in said

    [run] = listed(running)
    assert run["memory"] > 80_000_000
    assert run["size"] > 2_000_000
