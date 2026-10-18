import asyncio
from unittest import mock

from labnotes.tables.summarize_experiments import summarize_experiments


def make_tables() -> mock.Mock:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=[{"name": "a"}])
    return tables


def test_summarizes_every_experiment_by_name() -> None:
    tables = make_tables()

    assert asyncio.run(summarize_experiments(tables)) == [{"name": "a"}]
    sql = tables.query.await_args.args[0]
    assert sql.rstrip().endswith("ORDER BY e.name")
    for column in ("last_run", "created", "files", "runs"):
        assert f"AS {column}" in sql
    assert "e.config" not in sql


def test_summarizes_one_experiment() -> None:
    tables = make_tables()

    asyncio.run(summarize_experiments(tables, "it's"))

    sql = tables.query.await_args.args[0]
    assert sql.endswith("WHERE e.name = 'it''s'")
    assert "e.display_name, e.config," in sql
