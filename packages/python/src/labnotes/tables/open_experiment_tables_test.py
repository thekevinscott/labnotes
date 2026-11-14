from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.experiments_ddl import experiments_ddl
from labnotes.tables.open_experiment_tables import open_experiment_tables
from labnotes.tables.open_tables import BLOCKS, FILES, LOGS, MEMORY, RUN_FILES, RUNS
from labnotes.tables.read_blocks import read_blocks
from labnotes.tables.read_experiment import read_experiment
from labnotes.tables.read_file import read_file
from labnotes.tables.read_log import read_log
from labnotes.tables.read_memory import read_memory
from labnotes.tables.read_run import read_run
from labnotes.tables.read_run_file import read_run_file


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
    with (
        mock.patch("labnotes.tables.open_experiment_tables.DirSQL") as dir_sql,
        mock.patch("labnotes.tables.open_experiment_tables.Table", side_effect=dict),
    ):
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
    project = config()
    open_experiment_tables(project, "exp")

    assert {name: t["ddl"] for name, t in tables(dirsql).items()} == {
        "files": FILES,
        "runs": RUNS,
        "logs": LOGS,
        "blocks": BLOCKS,
        "memory": MEMORY,
        "experiment_configs": experiments_ddl(project),
        "run_files": RUN_FILES,
    }


def test_reads_each_table_against_the_named_experiment(
    dirsql: mock.MagicMock,
) -> None:
    open_experiment_tables(config(), "exp")

    readers = {name: t["on_file"] for name, t in tables(dirsql).items()}
    root = Path("/p")
    expected = {
        "files": partial(read_file, root, "exp/files/", experiment="exp"),
        "runs": partial(read_run, root, "exp/runs/{run}", experiment="exp"),
        "logs": partial(read_log, root, "exp/runs/{run}", experiment="exp"),
        "blocks": partial(read_blocks, root, "exp/runs/{run}", experiment="exp"),
        "memory": partial(read_memory, root, "exp/runs/{run}", experiment="exp"),
        "experiment_configs": partial(
            read_experiment, root, "exp", experiment="exp", defaults={"a": 1}
        ),
        "run_files": partial(read_run_file, root, "exp/runs/{run}", experiment="exp"),
    }
    for name, reader in readers.items():
        assert isinstance(reader, partial)
        want = expected[name]
        assert (reader.func, reader.args, reader.keywords) == (
            want.func,
            want.args,
            want.keywords,
        )


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
