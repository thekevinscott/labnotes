import warnings

import pytest

from labnotes.experiment_runs import experiment_runs


def test_selects_an_experiments_runs_with_a_column_per_param() -> None:
    assert experiment_runs("it's", ["model", 'a"b']) == (
        "(SELECT *,"
        ' params ->> \'$."model"\' AS "model",'
        ' params ->> \'$."a""b"\' AS "a""b",'
        " strftime('%Y-%m-%d %H:%M:%S', created) AS started,"
        " CAST(round((julianday(ended) - julianday(created)) * 86400) AS INTEGER)"
        " AS duration"
        " FROM runs WHERE experiment = 'it''s')"
    )


def test_a_param_named_like_a_runs_column_keeps_the_runs_column() -> None:
    with pytest.warns(UserWarning) as caught:
        query = experiment_runs("e", ["id", "model", "command", "started", "duration"])

    assert query == (
        "(SELECT *,"
        ' params ->> \'$."model"\' AS "model",'
        " strftime('%Y-%m-%d %H:%M:%S', created) AS started,"
        " CAST(round((julianday(ended) - julianday(created)) * 86400) AS INTEGER)"
        " AS duration"
        " FROM runs WHERE experiment = 'e')"
    )
    [warning] = caught
    assert str(warning.message) == (
        "Params id, command, started, duration clash with runs columns;"
        " the runs column wins. Read them from params instead."
    )
    assert warning.filename == __file__


def test_warns_nothing_without_a_clash() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        experiment_runs("e", ["model"])
