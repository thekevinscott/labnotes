import asyncio
from unittest import mock

from labnotes.check_counts import check_counts


def test_keeps_a_rule_that_works() -> None:
    tables = mock.Mock(query=mock.AsyncMock(return_value=[]))
    summary = {"completed_run": "exit_code = 0", "runs_per_cell": 2}

    assert asyncio.run(check_counts(tables, "src", summary)) == summary
    tables.query.assert_awaited_once_with("SELECT (exit_code = 0) FROM src LIMIT 0")


def test_counts_nothing_and_says_why_when_the_rule_fails() -> None:
    tables = mock.Mock(query=mock.AsyncMock(side_effect=RuntimeError("syntax")))
    summary = {"completed_run": "nope =", "runs_per_cell": 2}

    assert asyncio.run(check_counts(tables, "src", summary)) == {
        "completed_run": "0",
        "runs_per_cell": 2,
        "counts_error": "nope = doesn't work: syntax",
    }
