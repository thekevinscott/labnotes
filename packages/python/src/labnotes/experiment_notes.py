from pathlib import Path

from dirsql import DirSQL

from labnotes.sql_quote import quote_string


async def experiment_notes(
    tables: DirSQL, root: Path, experiment: str, note: str | None = None
) -> list[dict[str, str]]:
    where = f"experiment = {quote_string(experiment)} AND filename LIKE '%.md'"
    if note is not None:
        where += f" AND filename = {quote_string(note)}"
    rows = await tables.query(
        f"SELECT filename, path, content FROM files WHERE {where} ORDER BY filename"
    )
    return [
        {
            "name": str(row["filename"]),
            "path": str(root / str(row["path"])),
            "content": str(row["content"] or ""),
        }
        for row in rows
    ]
