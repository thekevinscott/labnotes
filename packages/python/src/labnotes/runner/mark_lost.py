import json
import time
from pathlib import Path

from labnotes.runner.write_run_json import write_run_json
from labnotes.tables.iso_time import iso_time


def mark_lost(folder: Path) -> None:
    try:
        run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if (
        not isinstance(run, dict)
        or run.get("ended") is not None
        or run.get("exit_code") is not None
    ):
        return
    lost = {"ended": iso_time(time.time()), "ended_by": "lost"}
    run |= lost
    if invocations := run.get("invocations"):
        invocations[-1] |= lost
    write_run_json(folder, run)
