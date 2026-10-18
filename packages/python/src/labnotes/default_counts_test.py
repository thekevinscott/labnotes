from labnotes.default_counts import DEFAULT_COUNTS


def test_counts_runs_that_exited_0_and_are_not_excluded() -> None:
    assert DEFAULT_COUNTS == (
        "exit_code = 0 AND NOT coalesce(run ->> 'excluded', false)"
    )
