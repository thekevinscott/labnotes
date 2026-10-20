import asyncio
from unittest import mock

import pytest

from labnotes.nests_runs import nests_runs


@pytest.mark.parametrize(("found", "nested"), [([{"1": 1}], True), ([], False)])
def test_nests_when_an_invocation_has_several_runs(
    found: list[dict[str, object]], nested: bool
) -> None:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=found)

    assert asyncio.run(nests_runs(runs, "(source)")) is nested
    runs.query.assert_awaited_once_with(
        "SELECT 1 FROM (source) WHERE instr(id, '/') > 0"
        " GROUP BY substr(id, 1, instr(id, '/') - 1)"
        " HAVING COUNT(*) > 1 LIMIT 1"
    )
