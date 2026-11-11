from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.open_run_tables import open_run_tables
from labnotes.tables.open_tables import BLOCKS, LOGS, RUNS
from labnotes.tables.read_blocks import read_blocks
from labnotes.tables.read_log import read_log
from labnotes.tables.read_run import read_run

CONFIG = mock.Mock(experiment=None, root=Path("/p"), runs="data/{experiment}/{run}")
FOLDER = Path("/p/data/alpha/r1")


@pytest.fixture
def dirsql() -> Iterator[mock.MagicMock]:
    with (
        mock.patch("labnotes.tables.open_run_tables.DirSQL") as dir_sql,
        mock.patch("labnotes.tables.open_run_tables.Table", side_effect=dict),
    ):
        yield dir_sql


def test_watches_only_the_run_folder(dirsql: mock.MagicMock) -> None:
    assert open_run_tables(CONFIG, FOLDER) == dirsql.return_value

    assert dirsql.call_args.args == ("/p/data/alpha/r1",)
    assert dirsql.call_args.kwargs["no_ignore"] is True


def test_reads_the_runs_own_files_with_the_project_readers(
    dirsql: mock.MagicMock,
) -> None:
    open_run_tables(CONFIG, FOLDER)

    tables = {t["name"]: t for t in dirsql.call_args.kwargs["tables"]}
    assert {name: (t["ddl"], t["glob"]) for name, t in tables.items()} == {
        "runs": (RUNS, "run.json"),
        "logs": (LOGS, "std*"),
        "blocks": (BLOCKS, "log.jsonl"),
    }
    for name, reader in [
        ("runs", read_run),
        ("logs", read_log),
        ("blocks", read_blocks),
    ]:
        on_file = tables[name]["on_file"]
        assert isinstance(on_file, partial)
        assert (on_file.func, on_file.args, on_file.keywords) == (
            reader,
            (Path("/p"), "data/{experiment}/{run}"),
            {"experiment": None},
        )
