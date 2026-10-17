from dirsql import DirSQL

from labnotes.sql_quote import quote_string


async def list_experiment_runs(tables: DirSQL, name: str) -> list[dict[str, object]]:
    return await tables.query(
        "SELECT id, created, ended, exit_code, error, params, folder FROM runs"
        f" WHERE experiment = {quote_string(name)} ORDER BY created, id"
    )
