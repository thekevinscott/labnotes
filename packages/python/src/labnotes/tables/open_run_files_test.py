from pathlib import Path
from unittest import mock

from labnotes.tables.open_run_files import open_run_files

CONFIG = mock.Mock(experiment=None, root=Path("/p"), runs="data/{experiment}/{run}")


def test_indexes_every_file_below_the_folder_only() -> None:
    with (
        mock.patch("labnotes.tables.open_run_files.DirSQL") as dir_sql,
        mock.patch("labnotes.tables.open_run_files.Table", side_effect=dict),
        mock.patch("labnotes.tables.open_run_files.RUN_FILES", "run files ddl"),
        mock.patch("labnotes.tables.open_run_files.read_run_file") as read_run_file,
        mock.patch("labnotes.tables.open_run_files.partial") as partial,
    ):
        assert open_run_files(CONFIG, Path("/p/data/alpha")) == dir_sql.return_value

    assert dir_sql.call_args.args == ("/p/data/alpha",)
    assert dir_sql.call_args.kwargs["no_ignore"] is True
    assert dir_sql.call_args.kwargs["tables"] == [
        {
            "name": "run_files",
            "ddl": "run files ddl",
            "glob": "**",
            "on_file": partial.return_value,
        }
    ]
    partial.assert_called_once_with(
        read_run_file, Path("/p"), "data/{experiment}/{run}", experiment=None
    )
