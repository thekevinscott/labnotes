from dirsql import DirSQL

from labnotes.sql_quote import quote_string


async def list_runs(
    runs: DirSQL, study: str, completed_run: str
) -> list[dict[str, object]]:
    return await runs.query(
        f"SELECT ({completed_run}) AS labnotes_completed, * FROM runs"
        f" WHERE study = {quote_string(study)} ORDER BY 2 DESC"
    )
