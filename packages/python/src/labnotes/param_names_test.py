from labnotes.param_names import param_names


def test_names_the_params_in_config_order() -> None:
    assert param_names({"params": {"y": ["a"], "x": [1, 2]}}) == ["y", "x"]


def test_leaves_out_a_param_named_id() -> None:
    assert param_names({"params": {"id": [1], "a": 2}}) == ["a"]


def test_names_nothing_without_a_config() -> None:
    assert param_names(None) == []
