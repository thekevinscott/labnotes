from dirsql import DirSQL

from labnotes.sql_quote import quote_string


async def list_experiment_runs(
    tables: DirSQL, name: str, counts: str
) -> list[dict[str, object]]:
    try:
        return await tables.query(
            f"SELECT id, created, ended, exit_code, error, ({counts}) AS counted,"
            " params, folder FROM runs"
            f" WHERE experiment = {quote_string(name)} ORDER BY created, id"
        )
    except RuntimeError as error:
        raise ValueError(f"{name}: counts doesn't work: {error}") from error
