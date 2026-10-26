from labnotes.runner.in_subset import in_subset

CELL: dict[str, object] = {"model": "small", "n": 2, "warm": True}


def test_keeps_every_cell_with_no_subset() -> None:
    assert in_subset(CELL, {})


def test_keeps_a_cell_matching_every_param() -> None:
    assert in_subset(CELL, {"model": "small", "n": "2", "warm": "true"})


def test_drops_a_cell_missing_any_param() -> None:
    assert not in_subset(CELL, {"model": "small", "n": "1"})
