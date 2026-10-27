from labnotes.compose_experiment import compose_experiment


def test_the_layer_replaces_top_level_keys() -> None:
    assert compose_experiment(
        {"command": "a", "repeats": 2}, {"command": "b", "name": "N"}
    ) == {"command": "b", "repeats": 2, "name": "N"}


def test_params_merge_by_name_with_the_layer_winning() -> None:
    composed = compose_experiment(
        {"params": {"m": [1], "n": [2]}}, {"params": {"n": [3], "o": [4]}}
    )

    assert composed == {"params": {"m": [1], "n": [3], "o": [4]}}


def test_env_merges_by_name_with_the_layer_winning() -> None:
    assert compose_experiment(
        {"env": {"BASE": "a", "BOTH": "shared"}},
        {"env": {"BOTH": "own", "OWN": "b"}},
    ) == {"env": {"BASE": "a", "BOTH": "own", "OWN": "b"}}


def test_params_from_one_side_pass_through() -> None:
    assert compose_experiment({"params": {"m": [1]}}, {}) == {"params": {"m": [1]}}
    assert compose_experiment({}, {"params": {"m": [1]}}) == {"params": {"m": [1]}}


def test_a_bad_params_value_passes_through_for_validation() -> None:
    assert compose_experiment({"params": {"m": [1]}}, {"params": 3}) == {"params": 3}


def test_leaves_its_inputs_alone() -> None:
    base: dict[str, object] = {"params": {"m": [1]}}

    compose_experiment(base, {"params": {"n": [2]}})

    assert base == {"params": {"m": [1]}}
