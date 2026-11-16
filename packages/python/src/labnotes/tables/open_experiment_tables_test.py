from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.tables.open_experiment_tables import open_experiment_tables

MODULE = "labnotes.tables.open_experiment_tables"
READERS = [
    "read_blocks",
    "read_experiment",
    "read_file",
    "read_log",
    "read_memory",
    "read_run",
    "read_run_file",
]
DDLS = ["BLOCKS", "FILES", "LOGS", "MEMORY", "RUN_FILES", "RUNS"]


def config(**paths: str) -> mock.Mock:
    return mock.Mock(
        experiment=None,
        defaults={"a": 1},
        root=Path("/p"),
        **{
            "experiments": "{experiment}",
            "files": "{experiment}/files/",
            "runs": "{experiment}/runs/{run}",
            **paths,
        },
    )


@pytest.fixture
def dirsql() -> Iterator[mock.MagicMock]:
    with ExitStack() as stack:
        dir_sql = stack.enter_context(mock.patch(f"{MODULE}.DirSQL"))
        stack.enter_context(mock.patch(f"{MODULE}.Table", side_effect=dict))
        stack.enter_context(
            mock.patch(f"{MODULE}.experiments_ddl", lambda config: "experiment ddl")
        )
        for name in READERS:
            stack.enter_context(mock.patch(f"{MODULE}.{name}", mock.Mock(name=name)))
        for name in DDLS:
            stack.enter_context(mock.patch(f"{MODULE}.{name}", f"{name} ddl"))
        yield dir_sql


def tables(dirsql: mock.MagicMock) -> dict[str, dict[str, object]]:
    return {t["name"]: t for t in dirsql.call_args.kwargs["tables"]}


def test_roots_at_the_experiment_and_scans_ignored_files(
    dirsql: mock.MagicMock,
) -> None:
    assert open_experiment_tables(config(), "exp") == dirsql.return_value

    assert dirsql.call_args.args == ("/p/exp",)
    assert dirsql.call_args.kwargs["no_ignore"] is True


def test_globs_each_table_inside_the_experiment(dirsql: mock.MagicMock) -> None:
    open_experiment_tables(config(), "exp")

    assert {name: t["glob"] for name, t in tables(dirsql).items()} == {
        "files": "files/**",
        "runs": "runs/**/run.json",
        "logs": "runs/**/std*",
        "blocks": "runs/**/log.jsonl",
        "memory": "runs/**/memory.jsonl",
        "experiment_configs": "experiment.toml",
        "run_files": "runs/**/**",
    }


def test_defines_every_table(dirsql: mock.MagicMock) -> None:
    open_experiment_tables(config(), "exp")

    assert {name: t["ddl"] for name, t in tables(dirsql).items()} == {
        "files": "FILES ddl",
        "runs": "RUNS ddl",
        "logs": "LOGS ddl",
        "blocks": "BLOCKS ddl",
        "memory": "MEMORY ddl",
        "experiment_configs": "experiment ddl",
        "run_files": "RUN_FILES ddl",
    }


def reader(func: str, *args: object, **keywords: object) -> tuple[object, ...]:
    return (func, args, keywords)


def test_reads_each_table_against_the_named_experiment(
    dirsql: mock.MagicMock,
) -> None:
    open_experiment_tables(config(), "exp")

    readers: dict[str, Any] = {name: t["on_file"] for name, t in tables(dirsql).items()}
    root = Path("/p")
    expected = {
        "files": reader("read_file", root, "exp/files/", experiment="exp"),
        "runs": reader("read_run", root, "exp/runs/{run}", experiment="exp"),
        "logs": reader("read_log", root, "exp/runs/{run}", experiment="exp"),
        "blocks": reader("read_blocks", root, "exp/runs/{run}", experiment="exp"),
        "memory": reader("read_memory", root, "exp/runs/{run}", experiment="exp"),
        "experiment_configs": reader(
            "read_experiment", root, "exp", experiment="exp", defaults={"a": 1}
        ),
        "run_files": reader("read_run_file", root, "exp/runs/{run}", experiment="exp"),
    }
    assert {
        name: (found.func._extract_mock_name(), found.args, found.keywords)
        for name, found in readers.items()
    } == expected


def test_roots_at_the_deepest_folder_every_path_shares(
    dirsql: mock.MagicMock,
) -> None:
    open_experiment_tables(
        config(
            experiments="lab/{experiment}",
            files="lab/{experiment}/notes/*.md",
            runs="lab/{experiment}/out/{run}",
        ),
        "exp",
    )
    assert dirsql.call_args.args == ("/p/lab/exp",)
    assert tables(dirsql)["files"]["glob"] == "notes/*.md"
    assert tables(dirsql)["runs"]["glob"] == "out/**/run.json"


def test_falls_back_to_the_project_when_runs_live_elsewhere(
    dirsql: mock.MagicMock,
) -> None:
    open_experiment_tables(config(runs="runs/{experiment}/{run}"), "exp")

    assert dirsql.call_args.args == ("/p",)
    assert tables(dirsql)["runs"]["glob"] == "runs/exp/**/run.json"
    assert tables(dirsql)["files"]["glob"] == "exp/files/**"


def test_one_experiment_project_roots_at_the_project(dirsql: mock.MagicMock) -> None:
    open_experiment_tables(
        config(experiments="", files="files/", runs="runs/{run}"), "exp"
    )

    assert dirsql.call_args.args == ("/p",)
    assert tables(dirsql)["experiment_configs"]["glob"] == "experiment.toml"
    assert tables(dirsql)["runs"]["glob"] == "runs/**/run.json"
