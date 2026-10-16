import asyncio
from pathlib import Path

import pytest

from labnotes.open_runs import open_runs

CONFIG = """
[[table]]
name = "runs"
glob = "runs/*.json"
on-file = "cat"
ddl = "CREATE TABLE runs (study TEXT)"
"""


async def query_runs(folder: Path) -> list[dict[str, object]]:
    db = open_runs(folder)
    await db.ready()
    return await db.query("SELECT study FROM runs")


def test_uses_the_folders_dirsql_config_and_ignores_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("runs/\n", encoding="utf-8")
    (tmp_path / ".dirsql.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "one.json").write_text('{"study": "s1"}\n', encoding="utf-8")

    assert asyncio.run(query_runs(tmp_path)) == [{"study": "s1"}]


def test_requires_a_dirsql_config(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="dirsql config"):
        open_runs(tmp_path)
