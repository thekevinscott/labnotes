from pathlib import Path

from dirsql import DirSQL

from labnotes.utils.tree_rss import tree_rss


def field(name: str) -> str:
    return f"(SELECT content ->> '{name}' FROM './run.json' WHERE json_valid(content))"


USAGE = (
    "SELECT (SELECT SUM(size) FROM './**') AS size,"
    f" {field('pid')} AS pid, {field('pid_created')} AS created,"
    f" coalesce({field('ended')}, {field('exit_code')}, {field('error')}) AS done"
)


async def run_usage(folder: Path, running: bool) -> dict[str, int | None]:
    # Run folders are often gitignored (DVC, large outputs); size them anyway.
    [row] = await DirSQL(str(folder), tables=[], no_ignore=True).query(USAGE)
    pid, created = row["pid"], row["created"]
    memory = None
    if (
        running
        and row["done"] is None
        and isinstance(pid, int)
        and isinstance(created, int | float)
    ):
        memory = tree_rss(pid, created)
    return {"memory": memory, "size": row["size"]}
