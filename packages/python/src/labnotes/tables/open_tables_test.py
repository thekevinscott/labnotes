from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.open_tables import open_tables

CONFIG = mock.Mock(
    root=Path("/p"),
    experiments="notes/{experiment}",
    files="notes/{experiment}/*.md",
    runs="data/{experiment}/{run}",
)


@pytest.fixture
def dirsql() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.tables.open_tables.DirSQL") as dir_sql,
        mock.patch("labnotes.tables.open_tables.Table", side_effect=dict) as table,
    ):
        yield {"DirSQL": dir_sql, "Table": table}


def tables(dirsql: dict[str, mock.MagicMock]) -> dict[str, dict[str, object]]:
    return {t["name"]: t for t in dirsql["DirSQL"].call_args.kwargs["tables"]}


def test_scans_the_root_including_ignored_files(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    assert open_tables(CONFIG) == dirsql["DirSQL"].return_value

    assert dirsql["DirSQL"].call_args.args == ("/p",)
    assert dirsql["DirSQL"].call_args.kwargs["no_ignore"] is True


def test_globs_each_table_from_its_path(dirsql: dict[str, mock.MagicMock]) -> None:
    open_tables(CONFIG)

    assert {name: t["glob"] for name, t in tables(dirsql).items()} == {
        "files": "notes/*/*.md",
        "runs": "data/*/*/run.json",
        "experiment_configs": "notes/*/experiment.toml",
    }


def test_reads_each_table_with_the_root_and_its_path(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    open_tables(CONFIG)

    readers = {name: t["on_file"] for name, t in tables(dirsql).items()}
    assert all(isinstance(reader, partial) for reader in readers.values())
    assert {name: r.args for name, r in readers.items()} == {  # type: ignore[attr-defined]
        "files": (Path("/p"), "notes/{experiment}/*.md"),
        "runs": (Path("/p"), "data/{experiment}/{run}"),
        "experiment_configs": (Path("/p"), "notes/{experiment}"),
    }


def test_declares_the_experiments_view_after_files_and_runs(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    open_tables(CONFIG)

    names = list(tables(dirsql))
    assert names.index("experiment_configs") > names.index("runs")
    assert "CREATE VIEW experiments" in str(tables(dirsql)["experiment_configs"]["ddl"])


def test_experiments_fall_back_to_the_folder_for_a_display_name(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    open_tables(CONFIG)

    ddl = str(tables(dirsql)["experiment_configs"]["ddl"])
    assert "coalesce(experiment_configs.config ->> 'name', names.name)" in ddl


def test_runs_carry_exclusion(dirsql: dict[str, mock.MagicMock]) -> None:
    open_tables(CONFIG)

    ddl = str(tables(dirsql)["runs"]["ddl"])
    assert "excluded INTEGER, reason TEXT" in ddl
