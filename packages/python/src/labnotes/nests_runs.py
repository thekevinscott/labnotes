from dirsql import DirSQL


async def nests_runs(runs: DirSQL, source: str) -> bool:
    found = await runs.query(
        f"SELECT 1 FROM {source} WHERE instr(id, '/') > 0"
        " GROUP BY substr(id, 1, instr(id, '/') - 1)"
        " HAVING COUNT(*) > 1 LIMIT 1"
    )
    return bool(found)
