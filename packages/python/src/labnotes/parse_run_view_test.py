from collections.abc import Iterator
from unittest import mock

import pytest
from starlette.datastructures import QueryParams

from labnotes.parse_run_view import parse_run_view

COLUMNS = ["run_id", "model"]
EMPTY: dict[str, object] = {
    "sort": None,
    "descending": False,
    "status": None,
    "filters": {},
    "picked": {},
}
CHOICES = {"model": {"haiku": '"haiku"', "1": "1"}}


def fresh(text: str) -> str:
    """A copy that is equal but not identical, so `is` cannot stand in for `==`."""
    return "".join(list(text))


@pytest.fixture
def run_view() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.parse_run_view.RunView") as run_view:
        yield run_view


def test_defaults_to_no_sort_status_or_filters(run_view: mock.MagicMock) -> None:
    assert parse_run_view(QueryParams(), COLUMNS, {}) is run_view.return_value
    run_view.assert_called_once_with(**EMPTY)


def test_reads_sort_order_status_and_filters(run_view: mock.MagicMock) -> None:
    params = {
        "sort": "model",
        "order": fresh("desc"),
        "status": "complete",
        "f.model": " haiku ",
        "f.run_id": "",
    }

    parse_run_view(QueryParams(params), COLUMNS, {})

    run_view.assert_called_once_with(
        sort="model",
        descending=True,
        status="complete",
        filters={"model": "haiku"},
        picked={},
    )


def test_sorts_by_status(run_view: mock.MagicMock) -> None:
    parse_run_view(QueryParams({"sort": fresh("status")}), COLUMNS, {})

    assert run_view.call_args.kwargs["sort"] == "status"


def test_ignores_unknown_columns_orders_and_statuses(
    run_view: mock.MagicMock,
) -> None:
    params = {
        "sort": "secret",
        "order": "sideways",
        "status": "maybe",
        "f.secret": "x",
    }

    parse_run_view(QueryParams(params), COLUMNS, {})

    run_view.assert_called_once_with(**EMPTY)


def test_picks_any_of_several_known_values_for_a_choice_column(
    run_view: mock.MagicMock,
) -> None:
    params = QueryParams("f.model=haiku&f.model=1&f.model=opus&f.run_id=r")

    parse_run_view(params, COLUMNS, CHOICES)

    assert run_view.call_args.kwargs["filters"] == {"run_id": "r"}
    assert run_view.call_args.kwargs["picked"] == {
        "model": {"haiku": '"haiku"', "1": "1"}
    }


def test_drops_a_choice_column_with_no_known_values(run_view: mock.MagicMock) -> None:
    parse_run_view(QueryParams("f.model=opus"), COLUMNS, CHOICES)

    run_view.assert_called_once_with(**EMPTY)
