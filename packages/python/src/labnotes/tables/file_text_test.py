import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.file_text import file_text


@pytest.fixture
def dirsql() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.tables.file_text.DirSQL") as cls:
        cls.return_value.query = mock.AsyncMock(return_value=[{"content": "a = 1"}])
        yield cls


def test_reads_a_file_through_a_path_table(dirsql: mock.MagicMock) -> None:
    text = asyncio.run(file_text(Path("/p"), Path("/p/it's/experiment.toml")))

    assert text == "a = 1"
    dirsql.assert_called_once_with("/p", tables=[], no_ignore=True)
    dirsql.return_value.query.assert_awaited_once_with(
        "SELECT content FROM '/p/it''s/experiment.toml'"
    )


def test_returns_none_for_a_missing_file(dirsql: mock.MagicMock) -> None:
    dirsql.return_value.query.return_value = []

    assert asyncio.run(file_text(Path("/p"), Path("/p/nope.toml"))) is None


def test_reads_undecodable_text_as_empty(dirsql: mock.MagicMock) -> None:
    dirsql.return_value.query.return_value = [{"content": None}]

    assert asyncio.run(file_text(Path("/p"), Path("/p/bad.toml"))) == ""
