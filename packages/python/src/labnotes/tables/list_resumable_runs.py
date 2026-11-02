from dirsql import DirSQL

from labnotes.list_runs import UNFINISHED
from labnotes.sql_quote import quote_string


async def list_resumable_runs(
    tables: DirSQL, name: str, counts: str
) -> list[dict[str, object]]:
    # Ended badly: a nonzero or missing exit code, not merely uncounted.
    return await tables.query(
        f"SELECT id, params FROM runs WHERE experiment = {quote_string(name)}"
        f" AND NOT coalesce(({counts}), false) AND NOT {UNFINISHED}"
        " AND (exit_code IS NULL OR exit_code <> 0)"
        " AND NOT coalesce(run ->> 'excluded', false) ORDER BY created, id"
    )
