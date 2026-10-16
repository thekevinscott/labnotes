from labnotes.models import RunView
from labnotes.sort_href import sort_href


def test_sorts_ascending_first() -> None:
    assert sort_href(RunView(), "model") == "?sort=model#runs"


def test_flips_to_descending_on_the_sorted_column() -> None:
    assert sort_href(RunView(sort="model"), "model") == "?sort=model&order=desc#runs"


def test_flips_back_to_ascending() -> None:
    view = RunView(sort="model", descending=True)

    assert sort_href(view, "model") == "?sort=model#runs"


def test_keeps_status_and_filters() -> None:
    view = RunView(sort="model", status="complete", filters={"run_id": "a b"})

    assert sort_href(view, "run_id") == (
        "?sort=run_id&status=complete&f.run_id=a+b#runs"
    )
