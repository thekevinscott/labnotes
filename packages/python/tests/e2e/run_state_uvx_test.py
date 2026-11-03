import json
import os
import subprocess
import sys
from pathlib import Path


def test_uvx_run_leaves_replayable_state(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} -c pass"\n' "repeats = 2\n"
    )
    result = subprocess.run(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    [state] = list((root / "exp/runs/run-state").glob("*.jsonl"))
    events = [json.loads(line) for line in state.read_text().splitlines()]
    assert len(events[0]["runs"]) == 2
    assert {event["event"] for event in events} >= {
        "planned",
        "started",
        "ended",
        "idle",
    }
    assert all("at" in event for event in events)
