import asyncio
from unittest import mock

from labnotes.tables.list_experiment_runs import list_experiment_runs


def test_lists_an_experiments_runs_oldest_first() -> None:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=[{"id": "r"}])

    assert asyncio.run(list_experiment_runs(tables, "it's")) == [{"id": "r"}]
    sql = tables.query.await_args.args[0]
    assert "WHERE experiment = 'it''s'" in sql
    assert sql.endswith("ORDER BY created, id")


def test_includes_exclusion() -> None:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=[])

    asyncio.run(list_experiment_runs(tables, "a"))

    assert "excluded, reason," in tables.query.await_args.args[0]
