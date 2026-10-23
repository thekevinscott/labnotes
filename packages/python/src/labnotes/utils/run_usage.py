from pathlib import Path

from dirsql import DirSQL

from labnotes.utils.tree_rss import tree_rss

USAGE = (
    "SELECT (SELECT SUM(size) FROM './**') AS size,"
    " (SELECT content ->> 'pid' FROM './run.json' WHERE json_valid(content)) AS pid"
)


async def run_usage(folder: Path, running: bool) -> dict[str, int | None]:
    # Run folders are often gitignored (DVC, large outputs); size them anyway.
    [row] = await DirSQL(str(folder), tables=[], no_ignore=True).query(USAGE)
    pid = row["pid"]
    memory = tree_rss(pid) if running and isinstance(pid, int) else None
    return {"memory": memory, "size": row["size"]}
