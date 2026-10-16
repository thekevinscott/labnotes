from labnotes.models import RunView
from labnotes.parse_run_view import parse_run_view

COLUMNS = ["run_id", "model"]


def test_defaults_to_no_sort_status_or_filters() -> None:
    assert parse_run_view({}, COLUMNS) == RunView()


def test_reads_sort_order_status_and_filters() -> None:
    params = {
        "sort": "model",
        "order": "desc",
        "status": "complete",
        "f.model": " haiku ",
        "f.run_id": "",
    }

    assert parse_run_view(params, COLUMNS) == RunView(
        sort="model", descending=True, status="complete", filters={"model": "haiku"}
    )


def test_sorts_by_status() -> None:
    assert parse_run_view({"sort": "status"}, COLUMNS).sort == "status"


def test_ignores_unknown_columns_orders_and_statuses() -> None:
    params = {
        "sort": "secret",
        "order": "sideways",
        "status": "maybe",
        "f.secret": "x",
    }

    assert parse_run_view(params, COLUMNS) == RunView()
