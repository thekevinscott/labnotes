from dirsql import DirSQL

from labnotes.models import RunView
from labnotes.sql_quote import quote_identifier, quote_string


async def list_runs(
    runs: DirSQL, source: str, completed_run: str, view: RunView
) -> list[dict[str, object]]:
    where = []
    if view.status:
        negate = {"complete": "", "incomplete": "NOT "}[view.status]
        where.append(f"{negate}({completed_run})")
    where += [
        f"instr(lower(CAST({quote_identifier(column)} AS TEXT)),"
        f" lower({quote_string(value)})) > 0"
        for column, value in view.filters.items()
    ]
    filtered = f" WHERE {' AND '.join(where)}" if where else ""
    direction = "DESC" if view.descending else "ASC"
    if view.sort == "status":
        order = f"labnotes_completed {direction}"
    elif view.sort:
        order = f"{quote_identifier(view.sort)} {direction}"
    else:
        order = "2 DESC"
    return await runs.query(
        f"SELECT ({completed_run}) AS labnotes_completed, * FROM {source}"
        f"{filtered} ORDER BY {order}"
    )
