"""Read the running-cell count from run folders for a live daemon."""

from dirsql import DirSQL

from labnotes.daemon.client import daemon_socket
from labnotes.models import LabnotesConfig
from labnotes.sql_quote import quote_string


async def daemon_marker(
    tables: DirSQL, config: LabnotesConfig, name: str
) -> dict[str, object]:
    """Mark a live owner and count its unfinished cells from disk-backed rows."""
    if daemon_socket(config, name) is None:
        return {"daemon": False, "running_cells": 0}
    [row] = await tables.query(
        "SELECT count(*) AS running_cells FROM runs"
        f" WHERE experiment = {quote_string(name)} AND ended IS NULL"
    )
    return {"daemon": True, "running_cells": row["running_cells"]}
