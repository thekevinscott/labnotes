from labnotes.models import RunView


def test_a_run_view_starts_unsorted_and_unfiltered() -> None:
    view = RunView()

    assert (view.sort, view.descending, view.status) == (None, False, None)
    assert (view.filters, view.picked) == ({}, {})


def test_run_views_do_not_share_their_picks() -> None:
    view = RunView()
    view.picked["model"] = {"a": '"a"'}

    assert RunView().picked == {}
