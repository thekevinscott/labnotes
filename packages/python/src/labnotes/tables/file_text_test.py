import asyncio
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.file_text import file_text


@pytest.fixture
def tables() -> mock.MagicMock:
    tables = mock.MagicMock()
    tables.query = mock.AsyncMock(return_value=[{"content": "a = 1"}])
    return tables


def test_reads_a_file_through_the_given_tables(tables: mock.MagicMock) -> None:
    text = asyncio.run(file_text(tables, Path("/p/it's/experiment.toml")))

    assert text == "a = 1"
    tables.query.assert_awaited_once_with(
        "SELECT content FROM '/p/it''s/experiment.toml'"
    )


def test_returns_none_for_a_missing_file(tables: mock.MagicMock) -> None:
    tables.query.return_value = []

    assert asyncio.run(file_text(tables, Path("/p/nope.toml"))) is None


def test_reads_undecodable_text_as_empty(tables: mock.MagicMock) -> None:
    tables.query.return_value = [{"content": None}]

    assert asyncio.run(file_text(tables, Path("/p/bad.toml"))) == ""
