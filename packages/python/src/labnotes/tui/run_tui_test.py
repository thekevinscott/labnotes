from unittest import mock

import pytest

from labnotes.tui.run_tui import run_tui


def test_runs_the_app_and_returns_its_results() -> None:
    start = mock.Mock()
    with (
        mock.patch("labnotes.tui.run_tui.RunApp") as run_app,
        mock.patch("labnotes.tui.run_tui.RUN_COLUMNS", ("a", "b")),
    ):
        run_app.return_value.results = [{"exit_code": 0}]
        run_app.return_value.error = None
        run_app.return_value.farewell = None

        assert run_tui(start, "exp") == [{"exit_code": 0}]

    run_app.assert_called_once_with(
        start,
        "exp",
        ("a", "b"),
        config=None,
        experiment_config=None,
        daemon_request=None,
    )
    run_app.return_value.run.assert_called_once_with()


def test_prints_the_apps_farewell_after_it_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with mock.patch("labnotes.tui.run_tui.RunApp") as run_app:
        run_app.return_value.error = None
        run_app.return_value.farewell = "exp is still running."

        run_tui(None, "exp")

    assert capsys.readouterr().out == "exp is still running.\n"


def test_raises_the_error_that_stopped_the_app() -> None:
    with mock.patch("labnotes.tui.run_tui.RunApp") as run_app:
        run_app.return_value.error = ValueError("no daemon")
        run_app.return_value.farewell = None

        with pytest.raises(ValueError, match="^no daemon$"):
            run_tui(mock.Mock(), "exp")

    run_app.return_value.run.assert_called_once_with()
