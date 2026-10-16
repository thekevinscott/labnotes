import asyncio
from unittest import mock

import pytest

from labnotes.list_runs import list_runs
from labnotes.models import RunView


def query(view: RunView) -> str:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=[])
    asyncio.run(list_runs(runs, "s", "exit_code = 0", view))
    return str(runs.query.await_args.args[0])


def test_lists_a_studys_runs_newest_first_with_a_completed_flag() -> None:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=[{"labnotes_completed": 1, "run_id": "b"}])

    assert asyncio.run(list_runs(runs, "s", "exit_code = 0", RunView())) == [
        {"labnotes_completed": 1, "run_id": "b"}
    ]
    sql = runs.query.await_args.args[0]
    assert sql.startswith("SELECT (exit_code = 0) AS labnotes_completed, * FROM runs")
    assert sql.endswith("WHERE study = 's' ORDER BY 2 DESC")


@pytest.mark.parametrize(
    ("view", "order"),
    [
        (RunView(sort="model"), 'ORDER BY "model" ASC'),
        (RunView(sort="model", descending=True), 'ORDER BY "model" DESC'),
        (RunView(sort="status"), "ORDER BY labnotes_completed ASC"),
    ],
)
def test_sorts_by_the_chosen_column(view: RunView, order: str) -> None:
    assert query(view).endswith(order)


@pytest.mark.parametrize(
    ("status", "condition"),
    [
        ("complete", " AND (exit_code = 0) "),
        ("incomplete", " AND NOT (exit_code = 0) "),
    ],
)
def test_filters_by_status(status: str, condition: str) -> None:
    assert condition in query(RunView(status=status))


def test_filters_columns_by_case_insensitive_substring() -> None:
    sql = query(RunView(filters={"model": "it's", "effort": "hi"}))

    assert (
        "WHERE study = 's'"
        " AND instr(lower(CAST(\"model\" AS TEXT)), lower('it''s')) > 0"
        " AND instr(lower(CAST(\"effort\" AS TEXT)), lower('hi')) > 0"
        " ORDER BY"
    ) in sql
