from dirsql import DirSQL

INVOCATION = (
    "CASE WHEN instr(id, '/') > 0 THEN substr(id, 1, instr(id, '/') - 1) ELSE id END"
)


async def count_groups(runs: DirSQL, source: str) -> dict[str, int]:
    found = await runs.query(
        f"SELECT {INVOCATION} AS invocation, COUNT(*) AS runs"
        f" FROM {source} GROUP BY invocation"
    )
    return {str(row["invocation"]): int(str(row["runs"])) for row in found}
