from dirsql import DirSQL


async def run_columns(runs: DirSQL) -> list[str]:
    rows = await runs.query("SELECT name FROM pragma_table_info('runs')")
    return [str(row["name"]) for row in rows]
