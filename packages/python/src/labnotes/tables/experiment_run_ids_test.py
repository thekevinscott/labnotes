import asyncio
from unittest import mock

from labnotes.tables.experiment_run_ids import experiment_run_ids


def test_lists_run_ids_and_the_groups_that_hold_them() -> None:
    tables = mock.Mock()
    tables.query = mock.AsyncMock(return_value=[{"id": "r1"}, {"id": "g1/n1"}])

    assert asyncio.run(experiment_run_ids(tables, "it's")) == {"r1", "g1/n1", "g1"}
    tables.query.assert_awaited_once_with(
        "SELECT id FROM runs WHERE experiment = 'it''s'"
    )
