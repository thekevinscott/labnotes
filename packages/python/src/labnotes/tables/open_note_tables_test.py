from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.open_note_tables import open_note_tables


@pytest.fixture
def dirsql() -> Iterator[mock.MagicMock]:
    with (
        mock.patch("labnotes.tables.open_note_tables.DirSQL") as dir_sql,
        mock.patch("labnotes.tables.open_note_tables.Table", side_effect=dict),
        mock.patch("labnotes.tables.open_note_tables.FILES", mock.sentinel.FILES),
        mock.patch(
            "labnotes.tables.open_note_tables.read_file", mock.sentinel.read_file
        ),
    ):
        yield dir_sql


def config(root: Path, files: str, experiment: str | None = None) -> mock.Mock:
    return mock.Mock(root=root, files=files, experiment=experiment)


@pytest.mark.parametrize(
    ("files", "folder", "glob"),
    [
        ("{experiment}/files/", "alpha/files", "**"),
        ("notes/{experiment}/*.md", "notes/alpha", "*.md"),
        ("notes/{experiment}-*.md", "notes", "*-*.md"),
    ],
)
def test_watches_only_the_experiments_notes_folder(
    dirsql: mock.MagicMock, tmp_path: Path, files: str, folder: str, glob: str
) -> None:
    (tmp_path / folder).mkdir(parents=True)

    assert open_note_tables(config(tmp_path, files), "alpha") == dirsql.return_value

    assert dirsql.call_args.args == (str(tmp_path / folder),)
    assert dirsql.call_args.kwargs["no_ignore"] is True
    [table] = dirsql.call_args.kwargs["tables"]
    assert (table["name"], table["ddl"], table["glob"]) == (
        "files",
        mock.sentinel.FILES,
        glob,
    )
    on_file = table["on_file"]
    assert isinstance(on_file, partial)
    assert (on_file.func, on_file.args, on_file.keywords) == (
        mock.sentinel.read_file,
        (tmp_path, files),
        {"experiment": None},
    )


def test_single_experiment_notes_sit_under_the_root(
    dirsql: mock.MagicMock, tmp_path: Path
) -> None:
    (tmp_path / "files").mkdir()

    open_note_tables(config(tmp_path, "files/", "solo"), "solo")

    assert dirsql.call_args.args == (str(tmp_path / "files"),)


def test_opens_nothing_without_a_notes_folder(
    dirsql: mock.MagicMock, tmp_path: Path
) -> None:
    assert open_note_tables(config(tmp_path, "{experiment}/files/"), "alpha") is None
    dirsql.assert_not_called()


def test_opens_nothing_outside_the_project(
    dirsql: mock.MagicMock, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    (tmp_path / "files").mkdir(parents=True)
    root.mkdir()

    assert open_note_tables(config(root, "{experiment}/files/"), "..") is None
    dirsql.assert_not_called()
