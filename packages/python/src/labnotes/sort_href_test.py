from unittest import mock

from labnotes.sort_href import sort_href


def make_view(
    sort: str | None = None,
    descending: bool = False,
    status: str | None = None,
    filters: dict[str, str] | None = None,
) -> mock.Mock:
    return mock.Mock(
        sort=sort, descending=descending, status=status, filters=filters or {}
    )


def test_sorts_ascending_first() -> None:
    assert sort_href(make_view(), "model") == "?sort=model#runs"


def test_flips_to_descending_on_the_sorted_column() -> None:
    assert sort_href(make_view(sort="model"), "model") == "?sort=model&order=desc#runs"


def test_flips_back_to_ascending() -> None:
    view = make_view(sort="model", descending=True)

    assert sort_href(view, "model") == "?sort=model#runs"


def test_keeps_status_and_filters() -> None:
    view = make_view(sort="model", status="complete", filters={"run_id": "a b"})

    assert sort_href(view, "run_id") == (
        "?sort=run_id&status=complete&f.run_id=a+b#runs"
    )
