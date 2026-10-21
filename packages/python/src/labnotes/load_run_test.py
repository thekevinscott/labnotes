import asyncio
from unittest import mock

from labnotes.load_run import load_run


def make_tables(rows: list[dict[str, object]]) -> mock.Mock:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=rows)
    return tables


def test_loads_one_run_with_its_experiments_name() -> None:
    tables = make_tables(
        [{"id": "g1/r1", "display_name": "Alpha", "params": '{"model": "opus"}'}]
    )

    run = asyncio.run(load_run(tables, "it's", "g1/r'1"))

    assert run == {"id": "g1/r1", "display_name": "Alpha", "params": {"model": "opus"}}
    assert tables.query.await_args.args[0] == (
        "SELECT runs.experiment, experiments.display_name, runs.id, runs.folder,"
        " runs.created, runs.ended, runs.exit_code, runs.error, runs.params"
        " FROM runs JOIN experiments ON experiments.name = runs.experiment"
        " WHERE runs.experiment = 'it''s' AND runs.id = 'g1/r''1'"
    )


def test_returns_none_for_an_unknown_run() -> None:
    assert asyncio.run(load_run(make_tables([]), "a", "nope")) is None
