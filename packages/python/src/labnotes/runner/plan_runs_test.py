from labnotes.runner.plan_runs import plan_runs

A: dict[str, object] = {"m": "a"}
B: dict[str, object] = {"m": "b"}


def test_goes_round_robin_over_cells() -> None:
    assert plan_runs([A, B], 2, []) == [A, B, A, B]


def test_counts_finished_runs_toward_repeats() -> None:
    assert plan_runs([A, B], 3, [A, A, B]) == [A, B, B]


def test_ignores_extra_finished_runs() -> None:
    assert plan_runs([A, B], 1, [A, A]) == [B]
