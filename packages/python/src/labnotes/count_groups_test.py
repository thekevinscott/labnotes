import asyncio
from unittest import mock

from labnotes.count_groups import count_groups


def test_counts_every_run_in_each_invocation() -> None:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(
        return_value=[{"invocation": "a", "runs": 3}, {"invocation": "b", "runs": 1}]
    )

    assert asyncio.run(count_groups(runs, "(source)")) == {"a": 3, "b": 1}
    sql = runs.query.await_args.args[0]
    assert "substr(id, 1, instr(id, '/') - 1) ELSE id END AS invocation" in sql
    assert sql.endswith("FROM (source) GROUP BY invocation")
