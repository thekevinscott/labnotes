import json
import os
import time
from pathlib import Path

from labnotes.list_runs import UNFINISHED
from labnotes.models import LabnotesConfig
from labnotes.runner.claim_run import LOCK_FILE, claim_run
from labnotes.runner.write_run_json import write_run_json
from labnotes.tables.iso_time import iso_time
from labnotes.tables.open_tables import open_tables
from labnotes.utils.process_alive import process_alive


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


async def finalize_lost_runs(config: LabnotesConfig) -> None:
    rows = await open_tables(config).query(
        f"SELECT folder, run FROM runs WHERE {UNFINISHED}"
    )
    for row in rows:
        folder = config.root / str(row["folder"])
        if (folder / LOCK_FILE).exists():
            lock = claim_run(folder)
            if lock is None:
                continue
            try:
                mark_lost(folder)
            finally:
                os.close(lock)
        else:
            run = json.loads(str(row["run"]))
            pid, created = run.get("pid"), run.get("pid_created")
            if isinstance(pid, int) and process_alive(
                pid, created if isinstance(created, int | float) else None
            ):
                continue
            mark_lost(folder)
