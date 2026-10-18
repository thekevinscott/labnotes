import asyncio
from unittest import mock

import pytest

from labnotes.tables.list_experiment_runs import list_experiment_runs


def test_lists_an_experiments_runs_oldest_first() -> None:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=[{"id": "r"}])

    assert asyncio.run(list_experiment_runs(tables, "it's", "x")) == [{"id": "r"}]
    sql = tables.query.await_args.args[0]
    assert "WHERE experiment = 'it''s'" in sql
    assert sql.endswith("ORDER BY created, id")


def test_marks_the_runs_that_count() -> None:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=[])

    asyncio.run(list_experiment_runs(tables, "a", "exit_code = 0"))

    assert (
        "error, (exit_code = 0) AS counted, params," in tables.query.await_args.args[0]
    )


def test_names_a_counts_that_does_not_work() -> None:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(side_effect=RuntimeError("syntax error"))

    with pytest.raises(ValueError, match="^a: counts doesn't work: syntax error$"):
        asyncio.run(list_experiment_runs(tables, "a", "(("))
