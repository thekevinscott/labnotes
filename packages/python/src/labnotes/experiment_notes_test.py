import asyncio
from pathlib import Path
from unittest import mock

from labnotes.experiment_notes import experiment_notes


def make_tables(rows: list[dict[str, object]]) -> mock.Mock:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=rows)
    return tables


def test_reads_an_experiments_markdown_files_from_the_tables() -> None:
    tables = make_tables(
        [
            {"filename": "PLAN.md", "path": "a/files/PLAN.md", "content": "plan ✓"},
            {"filename": "bad.md", "path": "a/files/bad.md", "content": None},
        ]
    )

    notes = asyncio.run(experiment_notes(tables, Path("/p"), "it's"))

    assert notes == [
        {"name": "PLAN.md", "path": "/p/a/files/PLAN.md", "content": "plan ✓"},
        {"name": "bad.md", "path": "/p/a/files/bad.md", "content": ""},
    ]
    assert tables.query.await_args.args[0] == (
        "SELECT filename, path, content FROM files"
        " WHERE experiment = 'it''s' AND filename LIKE '%.md' ORDER BY filename"
    )


def test_picks_one_note() -> None:
    tables = make_tables([])

    assert asyncio.run(experiment_notes(tables, Path("/p"), "a", "it's.md")) == []
    assert "AND filename = 'it''s.md' ORDER BY" in tables.query.await_args.args[0]
