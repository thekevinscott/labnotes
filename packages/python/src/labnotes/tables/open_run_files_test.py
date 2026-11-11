from functools import partial
from pathlib import Path
from unittest import mock

from labnotes.tables.open_run_files import open_run_files
from labnotes.tables.open_tables import RUN_FILES
from labnotes.tables.read_run_file import read_run_file

CONFIG = mock.Mock(experiment=None, root=Path("/p"), runs="data/{experiment}/{run}")


def test_indexes_every_file_below_the_folder_only() -> None:
    with (
        mock.patch("labnotes.tables.open_run_files.DirSQL") as dir_sql,
        mock.patch("labnotes.tables.open_run_files.Table", side_effect=dict),
    ):
        assert open_run_files(CONFIG, Path("/p/data/alpha")) == dir_sql.return_value

    assert dir_sql.call_args.args == ("/p/data/alpha",)
    assert dir_sql.call_args.kwargs["no_ignore"] is True
    [table] = dir_sql.call_args.kwargs["tables"]
    assert {key: table[key] for key in ("name", "ddl", "glob")} == {
        "name": "run_files",
        "ddl": RUN_FILES,
        "glob": "**",
    }
    reader = table["on_file"]
    assert isinstance(reader, partial)
    assert (reader.func, reader.args, reader.keywords) == (
        read_run_file,
        (Path("/p"), "data/{experiment}/{run}"),
        {"experiment": None},
    )
