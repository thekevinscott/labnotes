from labnotes.runner.param_grid import param_grid


def test_crosses_every_param() -> None:
    assert param_grid({"m": ["a", "b"], "e": [1, 2]}) == [
        {"m": "a", "e": 1},
        {"m": "a", "e": 2},
        {"m": "b", "e": 1},
        {"m": "b", "e": 2},
    ]


def test_has_one_empty_cell_without_params() -> None:
    assert param_grid({}) == [{}]
