from unittest import mock

from labnotes.tui.run_tui import run_tui


def test_runs_the_app_and_returns_its_results() -> None:
    start = mock.Mock()
    with mock.patch("labnotes.tui.run_tui.RunApp") as run_app:
        run_app.return_value.results = [{"exit_code": 0}]

        assert run_tui(start, "exp") == [{"exit_code": 0}]

    run_app.assert_called_once_with(start, "exp")
    run_app.return_value.run.assert_called_once_with()
