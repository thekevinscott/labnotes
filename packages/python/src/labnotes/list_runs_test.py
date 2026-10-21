import asyncio
from unittest import mock

import pytest

from labnotes.list_runs import list_runs


def make_view(
    sort: str | None = None,
    descending: bool = False,
    status: str | None = None,
    filters: dict[str, str] | None = None,
    picked: dict[str, dict[str, str]] | None = None,
) -> mock.Mock:
    return mock.Mock(
        sort=sort,
        descending=descending,
        status=status,
        filters=filters or {},
        picked=picked or {},
    )


def fresh(text: str) -> str:
    """A copy that is equal but not identical, so `is` cannot stand in for `==`."""
    return "".join(list(text))


def query(view: mock.Mock) -> str:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=[])
    asyncio.run(list_runs(runs, "(source)", "exit_code = 0", view))
    return str(runs.query.await_args.args[0])


def test_lists_runs_newest_first_with_a_completed_flag() -> None:
    runs = mock.Mock()
    runs.query = mock.AsyncMock(return_value=[{"labnotes_completed": 1, "run_id": "b"}])

    assert asyncio.run(list_runs(runs, "(source)", "exit_code = 0", make_view())) == [
        {"labnotes_completed": 1, "run_id": "b"}
    ]
    sql = runs.query.await_args.args[0]
    assert (
        sql == "SELECT (exit_code = 0) AS labnotes_completed,"
        " (ended IS NULL AND exit_code IS NULL AND error IS NULL) AS labnotes_unfinished,"
        " * FROM (source) ORDER BY created DESC, id DESC"
    )


@pytest.mark.parametrize(
    ("view", "order"),
    [
        (make_view(sort="model"), 'ORDER BY "model" ASC'),
        (make_view(sort="model", descending=True), 'ORDER BY "model" DESC'),
        (make_view(sort=fresh("status")), "ORDER BY labnotes_completed ASC"),
    ],
)
def test_sorts_by_the_chosen_column(view: mock.Mock, order: str) -> None:
    assert query(view).endswith(order)


@pytest.mark.parametrize(
    ("status", "condition"),
    [
        ("complete", "(source) WHERE (exit_code = 0) "),
        ("incomplete", "(source) WHERE NOT (exit_code = 0) "),
    ],
)
def test_filters_by_status(status: str, condition: str) -> None:
    assert condition in query(make_view(status=fresh(status)))


def test_filters_columns_by_case_insensitive_substring() -> None:
    sql = query(make_view(filters={"model": "it's", "effort": "hi"}))

    assert (
        "(source) WHERE instr(lower(CAST(\"model\" AS TEXT)), lower('it''s')) > 0"
        " AND instr(lower(CAST(\"effort\" AS TEXT)), lower('hi')) > 0"
        " ORDER BY"
    ) in sql


def test_filters_choice_columns_to_any_picked_json_value() -> None:
    sql = query(
        make_view(
            filters={"id": "r"},
            picked={"it's": {"a": '"a"', "1": "1"}, "m": {"b": '"b"'}},
        )
    )

    assert (
        "(source) WHERE instr(lower(CAST(\"id\" AS TEXT)), lower('r')) > 0"
        " AND params -> '$.\"it''s\"' IN ('\"a\"', '1')"
        " AND params -> '$.\"m\"' IN ('\"b\"')"
        " ORDER BY"
    ) in sql
