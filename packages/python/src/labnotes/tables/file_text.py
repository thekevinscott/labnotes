from pathlib import Path

from dirsql import DirSQL

from labnotes.sql_quote import quote_string


async def file_text(root: Path, path: Path) -> str | None:
    rows = await DirSQL(str(root), tables=[], no_ignore=True).query(
        f"SELECT content FROM {quote_string(str(path))}"
    )
    return str(rows[0]["content"] or "") if rows else None
