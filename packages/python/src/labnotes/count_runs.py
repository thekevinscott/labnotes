from dirsql import DirSQL

from labnotes.sql_quote import quote_identifier


async def count_runs(
    runs: DirSQL, source: str, completed_run: str, group_by: list[str] | None = None
) -> list[dict[str, object]]:
    keys = [quote_identifier(key) for key in group_by or []]
    columns = "".join(f"{key}, " for key in keys)
    group = f" GROUP BY {', '.join(keys)}" if keys else ""
    return await runs.query(
        f"SELECT {columns}COUNT(*) AS runs,"
        f" COALESCE(SUM(CASE WHEN ({completed_run}) THEN 1 ELSE 0 END), 0) AS completed"
        f" FROM {source}{group}"
    )
