from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.open_tables import open_tables

CONFIG = mock.Mock(
    experiment=None,
    defaults={},
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
        "runs": "data/*/**/run.json",
        "logs": "data/*/**/std*.log",
        "blocks": "data/*/**/log.jsonl",
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
        "logs": (Path("/p"), "data/{experiment}/{run}"),
        "blocks": (Path("/p"), "data/{experiment}/{run}"),
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
    assert "coalesce(config ->> 'name', name)" in ddl


def test_runs_carry_exclusion(dirsql: dict[str, mock.MagicMock]) -> None:
    open_tables(CONFIG)

    ddl = str(tables(dirsql)["runs"]["ddl"])
    assert "params TEXT, meta TEXT, command TEXT, run TEXT" in ddl


def test_experiments_carry_the_config_source(dirsql: dict[str, mock.MagicMock]) -> None:
    open_tables(CONFIG)

    ddl = str(tables(dirsql)["experiment_configs"]["ddl"])
    assert "config TEXT, source TEXT" in ddl
    assert "experiment_configs.source\n" in ddl


def test_files_carry_a_nanosecond_mtime_so_quick_edits_change_the_row(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    open_tables(CONFIG)

    assert "mtime_ns INTEGER" in str(tables(dirsql)["files"]["ddl"])


def test_files_hold_note_text(dirsql: dict[str, mock.MagicMock]) -> None:
    open_tables(CONFIG)

    assert "content TEXT" in str(tables(dirsql)["files"]["ddl"])


def test_logs_carry_only_their_size(dirsql: dict[str, mock.MagicMock]) -> None:
    open_tables(CONFIG)

    ddl = str(tables(dirsql)["logs"]["ddl"])
    assert "stream TEXT, size INTEGER" in ddl
    assert "PRIMARY KEY (experiment, run, stream)" in ddl


def test_block_logs_carry_only_their_size(dirsql: dict[str, mock.MagicMock]) -> None:
    open_tables(CONFIG)

    ddl = str(tables(dirsql)["blocks"]["ddl"])
    assert "run TEXT, size INTEGER" in ddl
    assert "PRIMARY KEY (experiment, run)" in ddl


def test_names_rows_after_the_one_experiment(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    config = mock.Mock(
        experiment="study",
        defaults={},
        root=Path("/p"),
        experiments="",
        files="notes/",
        runs="runs/{run}",
    )

    open_tables(config)

    found = tables(dirsql)
    assert found["experiment_configs"]["glob"] == "experiment.toml"
    assert {name: t["on_file"].keywords for name, t in found.items()} == {  # type: ignore[attr-defined]
        "files": {"experiment": "study"},
        "runs": {"experiment": "study"},
        "logs": {"experiment": "study"},
        "blocks": {"experiment": "study"},
        "experiment_configs": {"experiment": "study", "defaults": {}},
    }


def test_experiments_without_a_config_fall_back_to_the_defaults(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    config = mock.Mock(
        experiment=None,
        defaults={"command": "it's"},
        root=Path("/p"),
        experiments="{experiment}",
        files="{experiment}/files/",
        runs="{experiment}/runs/{run}",
    )

    open_tables(config)

    ddl = str(tables(dirsql)["experiment_configs"]["ddl"])
    assert """coalesce(experiment_configs.config, '{"command": "it''s"}')""" in ddl
    assert "UNION SELECT experiment FROM runs\n" in ddl


def test_lists_the_one_experiment_even_with_nothing_on_disk(
    dirsql: dict[str, mock.MagicMock],
) -> None:
    config = mock.Mock(
        experiment="study",
        defaults={},
        root=Path("/p"),
        experiments="",
        files="files/",
        runs="runs/{run}",
    )

    open_tables(config)

    ddl = str(tables(dirsql)["experiment_configs"]["ddl"])
    assert "coalesce(experiment_configs.config, NULL)" in ddl
    assert "UNION SELECT experiment FROM runs\n      UNION SELECT 'study'\n" in ddl
