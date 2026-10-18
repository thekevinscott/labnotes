import asyncio
from pathlib import Path
from unittest import mock

from labnotes.experiment_notes import experiment_notes


def make_tables(rows: list[dict[str, object]]) -> mock.Mock:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=rows)
    return tables


def test_reads_an_experiments_markdown_files(tmp_path: Path) -> None:
    (tmp_path / "a" / "files").mkdir(parents=True)
    (tmp_path / "a/files/PLAN.md").write_text("plan ✓", encoding="utf-8")
    tables = make_tables([{"filename": "PLAN.md", "path": "a/files/PLAN.md"}])

    notes = asyncio.run(experiment_notes(tables, tmp_path, "it's"))

    assert notes == [{"name": "PLAN.md", "content": "plan ✓"}]
    assert tables.query.await_args.args[0] == (
        "SELECT filename, path FROM files"
        " WHERE experiment = 'it''s' AND filename LIKE '%.md' ORDER BY filename"
    )


def test_picks_one_note() -> None:
    tables = make_tables([])

    assert asyncio.run(experiment_notes(tables, Path("/p"), "a", "it's.md")) == []
    assert "AND filename = 'it''s.md' ORDER BY" in tables.query.await_args.args[0]
