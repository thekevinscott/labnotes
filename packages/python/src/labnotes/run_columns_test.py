import asyncio
from unittest import mock

from labnotes.run_columns import run_columns


def test_lists_the_runs_table_columns() -> None:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=[{"name": "run_id"}, {"name": "study"}])

    assert asyncio.run(run_columns(runs)) == ["run_id", "study"]
    assert "pragma_table_info('runs')" in runs.query.await_args.args[0]
