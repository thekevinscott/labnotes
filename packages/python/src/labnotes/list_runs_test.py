import asyncio
from unittest import mock

from labnotes.list_runs import list_runs


def test_lists_a_studys_runs_newest_first_with_a_completed_flag() -> None:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=[{"labnotes_completed": 1, "run_id": "b"}])

    assert asyncio.run(list_runs(runs, "s", "exit_code = 0")) == [
        {"labnotes_completed": 1, "run_id": "b"}
    ]
    sql = runs.query.await_args.args[0]
    assert sql.startswith("SELECT (exit_code = 0) AS labnotes_completed, * FROM runs")
    assert sql.endswith("WHERE study = 's' ORDER BY 2 DESC")
