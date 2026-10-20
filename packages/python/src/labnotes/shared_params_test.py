from labnotes.shared_params import shared_params


def test_shares_a_value_every_run_has() -> None:
    assert shared_params([{"m": "a"}, {"m": "a"}], ["m"]) == {"m": "a"}


def test_shares_nothing_the_runs_differ_on() -> None:
    assert shared_params([{"m": "a"}, {"m": "b"}], ["m"]) == {}


def test_shares_only_the_params_asked_about() -> None:
    assert shared_params([{"m": "a", "n": 1}], ["m"]) == {"m": "a"}
