import json
import os
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_leaves_replayable_state(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} -c pass"\n' "repeats = 2\n"
    )

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=120)
    tui.quit(term)
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
