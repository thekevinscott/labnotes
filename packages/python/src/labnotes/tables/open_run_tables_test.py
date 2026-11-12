from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.open_run_tables import open_run_tables

CONFIG = mock.Mock(experiment=None, root=Path("/p"), runs="data/{experiment}/{run}")
FOLDER = Path("/p/data/alpha/r1")


MODULE = "labnotes.tables.open_run_tables"
COLLABORATORS = ("RUNS", "LOGS", "BLOCKS", "read_run", "read_log", "read_blocks")


@pytest.fixture
def dirsql() -> Iterator[mock.MagicMock]:
    with (
        mock.patch(f"{MODULE}.DirSQL") as dir_sql,
        mock.patch(f"{MODULE}.Table", side_effect=dict),
    ):
        yield dir_sql


@pytest.fixture
def stand_ins() -> Iterator[dict[str, mock.Mock]]:
    found = {name: mock.Mock(name=name) for name in COLLABORATORS}
    with mock.patch.multiple(MODULE, **found):
        yield found


def test_watches_only_the_run_folder(dirsql: mock.MagicMock) -> None:
    assert open_run_tables(CONFIG, FOLDER) == dirsql.return_value

    assert dirsql.call_args.args == ("/p/data/alpha/r1",)
    assert dirsql.call_args.kwargs["no_ignore"] is True


def test_reads_the_runs_own_files_with_the_project_readers(
    dirsql: mock.MagicMock, stand_ins: dict[str, mock.Mock]
) -> None:
    open_run_tables(CONFIG, FOLDER)

    tables = {t["name"]: t for t in dirsql.call_args.kwargs["tables"]}
    assert {name: (t["ddl"], t["glob"]) for name, t in tables.items()} == {
        "runs": (stand_ins["RUNS"], "run.json"),
        "logs": (stand_ins["LOGS"], "std*"),
        "blocks": (stand_ins["BLOCKS"], "log.jsonl"),
    }
    for name, reader in [
        ("runs", "read_run"),
        ("logs", "read_log"),
        ("blocks", "read_blocks"),
    ]:
        on_file = tables[name]["on_file"]
        assert isinstance(on_file, partial)
        assert (on_file.func, on_file.args, on_file.keywords) == (
            stand_ins[reader],
            (Path("/p"), "data/{experiment}/{run}"),
            {"experiment": None},
        )
