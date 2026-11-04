from dirsql import DirSQL

from labnotes.list_runs import UNFINISHED
from labnotes.sql_quote import quote_string


async def list_resumable_runs(
    tables: DirSQL, name: str, counts: str
) -> list[dict[str, object]]:
    # Ended badly: a nonzero or missing exit code, not merely uncounted.
    # Invocations stopped by hand don't spend retries.
    return await tables.query(
        "SELECT id, params, CASE WHEN json_type(run, '$.invocations') = 'array'"
        " THEN (SELECT count(*) FROM json_each(run, '$.invocations')"
        " WHERE json_extract(value, '$.ended_by') IS NOT 'stop')"
        " ELSE json_extract(run, '$.ended_by') IS NOT 'stop' END AS invocations"
        f" FROM runs WHERE experiment = {quote_string(name)}"
        f" AND NOT coalesce(({counts}), false) AND NOT {UNFINISHED}"
        " AND (exit_code IS NULL OR exit_code <> 0)"
        " AND NOT coalesce(run ->> 'excluded', false) ORDER BY created, id"
    )
