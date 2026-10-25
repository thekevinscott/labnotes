import sqlite3
from functools import cache

from labnotes.tables.open_tables import RUNS


@cache
def runs_columns() -> tuple[str, ...]:
    with sqlite3.connect(":memory:") as db:
        db.execute(RUNS)
        return tuple(row[1] for row in db.execute("PRAGMA table_info(runs)"))
