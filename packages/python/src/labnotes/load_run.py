import json

from dirsql import DirSQL

from labnotes.sql_quote import quote_string


async def load_run(
    tables: DirSQL, experiment: str, run: str
) -> dict[str, object] | None:
    rows = await tables.query(
        "SELECT runs.experiment, experiments.display_name, runs.id, runs.folder,"
        " runs.created, runs.ended, runs.exit_code, runs.error, runs.params"
        " FROM runs JOIN experiments ON experiments.name = runs.experiment"
        f" WHERE runs.experiment = {quote_string(experiment)}"
        f" AND runs.id = {quote_string(run)}"
    )
    if not rows:
        return None
    [row] = rows
    return {**row, "params": json.loads(str(row["params"]))}
