from unittest import mock

from labnotes.run_columns import run_columns


def test_shows_the_id_then_the_params_then_the_times() -> None:
    with mock.patch(
        "labnotes.run_columns.param_names", return_value=["x", "y"]
    ) as param_names:
        assert run_columns({"params": {}}) == ["id", "x", "y", "started", "duration"]

    param_names.assert_called_once_with({"params": {}})
