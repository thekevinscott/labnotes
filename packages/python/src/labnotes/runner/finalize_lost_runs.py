import json
import os
from labnotes.list_runs import UNFINISHED
from labnotes.models import LabnotesConfig
from labnotes.runner.claim_run import LOCK_FILE, claim_run
from labnotes.runner.mark_lost import mark_lost
from labnotes.tables.open_tables import open_tables
from labnotes.utils.process_alive import process_alive


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
