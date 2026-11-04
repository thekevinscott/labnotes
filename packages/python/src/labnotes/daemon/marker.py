"""Read the running-cell count from run folders for a live daemon."""

from dirsql import DirSQL

from labnotes.daemon.client import daemon_socket
from labnotes.models import LabnotesConfig
from labnotes.runner.claim_run import LOCK_FILE
from labnotes.runner.run_locked import run_locked
from labnotes.sql_quote import quote_string


async def daemon_marker(
    tables: DirSQL, config: LabnotesConfig, name: str
) -> dict[str, object]:
    """Mark a live owner and count its unfinished cells from disk-backed rows."""
    if daemon_socket(config, name) is None:
        return {"daemon": False, "running_cells": 0}
    rows = await tables.query(
        "SELECT folder FROM runs"
        f" WHERE experiment = {quote_string(name)} AND ended IS NULL"
    )
    running = 0
    for row in rows:
        folder = config.root / str(row["folder"])
        if (folder / LOCK_FILE).exists() and run_locked(folder):
            running += 1
    return {"daemon": True, "running_cells": running}
