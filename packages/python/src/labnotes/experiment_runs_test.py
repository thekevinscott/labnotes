from labnotes.experiment_runs import experiment_runs


def test_selects_an_experiments_runs_with_a_column_per_param() -> None:
    assert experiment_runs("it's", ["model", 'a"b']) == (
        "(SELECT *,"
        ' params ->> \'$."model"\' AS "model",'
        ' params ->> \'$."a""b"\' AS "a""b"'
        " FROM runs WHERE experiment = 'it''s')"
    )
