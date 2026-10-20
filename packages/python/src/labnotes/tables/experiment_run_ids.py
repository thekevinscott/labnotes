from dirsql import DirSQL

from labnotes.sql_quote import quote_string


async def experiment_run_ids(tables: DirSQL, name: str) -> set[str]:
    rows = await tables.query(
        f"SELECT id FROM runs WHERE experiment = {quote_string(name)}"
    )
    ids = {str(row["id"]) for row in rows}
    return ids | {run.split("/")[0] for run in ids}
