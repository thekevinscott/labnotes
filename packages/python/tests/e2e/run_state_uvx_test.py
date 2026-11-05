from conftest import run_uvx_tui
import json
import os
import sys
from pathlib import Path


def test_uvx_run_leaves_replayable_state(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} -c pass"\n' "repeats = 2\n"
    )
    result = run_uvx_tui(root, uvx, "experiments", "exp", "run")
    assert result.returncode == 0, result.stdout + result.stderr
    [state] = list(
        (Path(os.environ["XDG_STATE_HOME"]) / "labnotes/run-state").glob("*/*.jsonl")
    )
    assert sorted(p.name for p in (root / "exp/runs").iterdir()) == sorted(
        p.parent.name for p in (root / "exp/runs").glob("*/run.json")
    )
    events = [json.loads(line) for line in state.read_text().splitlines()]
    assert len(events[0]["runs"]) == 2
    assert {event["event"] for event in events} >= {
        "planned",
        "started",
        "ended",
        "idle",
    }
    assert all("at" in event for event in events)
