from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.open_folder_files import FOLDER_FILES, open_folder_files

MODULE = "labnotes.tables.open_folder_files"


@pytest.fixture
def dirsql() -> Iterator[mock.MagicMock]:
    with (
        mock.patch(f"{MODULE}.DirSQL") as dir_sql,
        mock.patch(f"{MODULE}.Table", side_effect=dict),
        mock.patch(f"{MODULE}.read_folder_file") as read_folder_file,
    ):
        dir_sql.read_folder_file = read_folder_file
        yield dir_sql


def test_watches_every_file_under_the_folder(dirsql: mock.MagicMock) -> None:
    folder = Path("/p/runs/r1")

    assert open_folder_files(folder) == dirsql.return_value

    assert dirsql.call_args.args == ("/p/runs/r1",)
    assert dirsql.call_args.kwargs["no_ignore"] is True
    [table] = dirsql.call_args.kwargs["tables"]
    assert (table["name"], table["ddl"], table["glob"]) == ("files", FOLDER_FILES, "**")
    on_file = table["on_file"]
    assert isinstance(on_file, partial)
    assert (on_file.func, on_file.args) == (dirsql.read_folder_file, (folder,))


def test_the_table_keys_files_by_path() -> None:
    assert "path TEXT PRIMARY KEY" in FOLDER_FILES
    assert "size INTEGER" in FOLDER_FILES
