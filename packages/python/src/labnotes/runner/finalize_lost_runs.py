import json
import time

from labnotes.list_runs import UNFINISHED
from labnotes.models import LabnotesConfig
from labnotes.runner.claim_run import LOCK_FILE
from labnotes.runner.run_locked import run_locked
from labnotes.runner.write_run_json import write_run_json
from labnotes.tables.iso_time import iso_time
from labnotes.tables.open_tables import open_tables
from labnotes.utils.process_alive import process_alive


async def finalize_lost_runs(config: LabnotesConfig) -> None:
    rows = await open_tables(config).query(
        f"SELECT folder, run FROM runs WHERE {UNFINISHED}"
    )
    for row in rows:
        run = json.loads(str(row["run"]))
        folder = config.root / str(row["folder"])
        pid, created = run.get("pid"), run.get("pid_created")
        if (folder / LOCK_FILE).exists():
            if run_locked(folder):
                continue
        elif isinstance(pid, int) and process_alive(
            pid, created if isinstance(created, int | float) else None
        ):
            continue
        lost = {"ended": iso_time(time.time()), "ended_by": "lost"}
        run |= lost
        if invocations := run.get("invocations"):
            invocations[-1] |= lost
        write_run_json(folder, run)
