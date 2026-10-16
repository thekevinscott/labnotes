import asyncio
from unittest import mock

from labnotes.count_runs import count_runs


def make_runs() -> mock.Mock:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=[{"runs": 3, "completed": 2}])
    return runs


def test_counts_runs_and_completed_runs_for_a_study() -> None:
    runs = make_runs()

    assert asyncio.run(count_runs(runs, "it's", "exit_code = 0")) == [
        {"runs": 3, "completed": 2}
    ]
    sql = runs.query.await_args.args[0]
    assert "WHERE study = 'it''s'" in sql
    assert "WHEN (exit_code = 0)" in sql
    assert "GROUP BY" not in sql


def test_groups_by_quoted_columns() -> None:
    runs = make_runs()

    asyncio.run(count_runs(runs, "s", "1", group_by=["model", "effort"]))

    sql = runs.query.await_args.args[0]
    assert sql.startswith('SELECT "model", "effort", COUNT(*)')
    assert sql.endswith('GROUP BY "model", "effort"')
