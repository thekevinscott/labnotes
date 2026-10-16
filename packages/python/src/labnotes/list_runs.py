from dirsql import DirSQL

from labnotes.models import RunView
from labnotes.sql_quote import quote_identifier, quote_string


async def list_runs(
    runs: DirSQL, study: str, completed_run: str, view: RunView
) -> list[dict[str, object]]:
    where = [f"study = {quote_string(study)}"]
    if view.status:
        negate = "" if view.status == "complete" else "NOT "
        where.append(f"{negate}({completed_run})")
    where += [
        f"instr(lower(CAST({quote_identifier(column)} AS TEXT)),"
        f" lower({quote_string(value)})) > 0"
        for column, value in view.filters.items()
    ]
    direction = "DESC" if view.descending else "ASC"
    if view.sort == "status":
        order = f"labnotes_completed {direction}"
    elif view.sort:
        order = f"{quote_identifier(view.sort)} {direction}"
    else:
        order = "2 DESC"
    return await runs.query(
        f"SELECT ({completed_run}) AS labnotes_completed, * FROM runs"
        f" WHERE {' AND '.join(where)} ORDER BY {order}"
    )
