import asyncio
from unittest import mock

from labnotes.tables.list_resumable_runs import list_resumable_runs


def test_lists_runs_that_ended_badly_oldest_first() -> None:
    tables = mock.Mock(query=mock.AsyncMock(return_value=[{"id": "r1"}]))

    with mock.patch("labnotes.tables.list_resumable_runs.UNFINISHED", "unfinished"):
        rows = asyncio.run(list_resumable_runs(tables, "it's", "rule"))

    assert rows == [{"id": "r1"}]
    tables.query.assert_awaited_once_with(
        "SELECT id, params, folder, CASE WHEN json_type(run, '$.invocations') = 'array'"
        " THEN (SELECT count(*) FROM json_each(run, '$.invocations')"
        " WHERE coalesce(json_extract(value, '$.ended_by'), '') NOT IN ('stop', 'lost'))"
        " ELSE coalesce(json_extract(run, '$.ended_by'), '') NOT IN ('stop', 'lost')"
        " END AS invocations"
        " FROM runs WHERE experiment = 'it''s'"
        " AND NOT coalesce((rule), false) AND NOT unfinished"
        " AND (exit_code IS NULL OR exit_code <> 0)"
        " AND NOT coalesce(run ->> 'excluded', false) ORDER BY created, id"
    )
