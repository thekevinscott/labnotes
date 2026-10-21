from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.browse_tui import browse_tui


@pytest.fixture
def app() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.tui.browse_tui.BrowseApp") as browse_app:
        browse_app.return_value.run.return_value = None
        yield browse_app


def test_runs_the_browser(app: mock.MagicMock) -> None:
    config = mock.Mock()

    browse_tui(config, "alpha")

    app.assert_called_once_with(config, "alpha")
    app.return_value.run.assert_called_once_with()


def test_raises_what_stopped_the_browser(app: mock.MagicMock) -> None:
    app.return_value.run.return_value = ValueError("No experiment named zz.")

    with pytest.raises(ValueError, match="No experiment named zz."):
        browse_tui(mock.Mock(), "zz")
