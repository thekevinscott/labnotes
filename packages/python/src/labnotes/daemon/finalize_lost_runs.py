import json
import time

from labnotes.list_runs import UNFINISHED
from labnotes.models import LabnotesConfig
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
        pid, created = run.get("pid"), run.get("pid_created")
        if isinstance(pid, int) and process_alive(
            pid, created if isinstance(created, int | float) else None
        ):
            continue
        run |= {"ended": iso_time(time.time()), "ended_by": "lost"}
        write_run_json(config.root / str(row["folder"]), run)
