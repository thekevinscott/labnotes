from labnotes.cell_progress import cell_progress


def test_fills_every_cell_of_the_grid_including_empty_ones() -> None:
    varies: dict[str, list[object]] = {"model": ["a", "b"], "tests": [False, True]}
    counts: list[dict[str, object]] = [
        {"model": "a", "tests": 1, "runs": 4, "completed": 3},
    ]

    cells = cell_progress(varies, counts)

    assert len(cells) == 4
    assert cells[1] == {
        "values": {"model": "a", "tests": True},
        "runs": 4,
        "completed": 3,
    }
    assert cells[0] == {
        "values": {"model": "a", "tests": False},
        "runs": 0,
        "completed": 0,
    }
