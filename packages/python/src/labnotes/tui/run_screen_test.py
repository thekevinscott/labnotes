from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.run_screen import RunScreen

FOLDER = Path("/p/project/alpha/runs/first")


@pytest.fixture(autouse=True)
def widgets() -> Iterator[mock.MagicMock]:
    with (
        mock.patch("labnotes.tui.run_screen.Header", return_value="header"),
        mock.patch("labnotes.tui.run_screen.Footer", return_value="footer"),
        mock.patch(
            "labnotes.tui.run_screen.RunOutput", return_value="output"
        ) as run_output,
    ):
        yield run_output


@pytest.fixture
def output() -> mock.MagicMock:
    return mock.MagicMock()


@pytest.fixture
def screen(output: mock.MagicMock) -> Iterator[RunScreen]:
    shown = RunScreen("20261017-000000/first", FOLDER)
    with (
        mock.patch.object(shown, "query_one", return_value=output),
        mock.patch.object(shown, "set_interval"),
    ):
        yield shown


def test_shows_the_output_between_the_header_and_footer(
    screen: RunScreen, widgets: mock.MagicMock
) -> None:
    assert list(screen.compose()) == ["header", "output", "footer"]
    widgets.assert_called_once_with(id="output")


def test_binds_escape_to_go_back() -> None:
    assert [
        (binding.key, binding.action, binding.description)  # type: ignore[union-attr]
        for binding in RunScreen.BINDINGS
    ] == [("escape", "app.pop_screen", "Back")]


def test_names_the_run_and_follows_its_folder(
    screen: RunScreen, output: mock.MagicMock, widgets: mock.MagicMock
) -> None:
    screen.on_mount()

    assert screen.sub_title == "20261017-000000/first"
    getattr(screen.query_one, "assert_called_once_with")(widgets)
    output.follow.assert_called_once_with(FOLDER)
    getattr(screen.set_interval, "assert_called_once_with")(0.25, screen.follow)
