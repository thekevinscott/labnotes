from labnotes.modes import DEFAULT_MODE, MODES


def test_runs_ad_hoc_unless_told_to_fill() -> None:
    assert (MODES, DEFAULT_MODE) == (("matrix", "adhoc"), "adhoc")
