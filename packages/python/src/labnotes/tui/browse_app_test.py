import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.browse_app import BrowseApp

CONFIG = mock.Mock(root=Path("/p/project"), mode="matrix")


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.tui.browse_app.open_tables") as open_tables,
        mock.patch(
            "labnotes.tui.experiments_screen.summarize_experiments",
            new=mock.AsyncMock(return_value=[]),
        ),
        mock.patch(
            "labnotes.tui.experiment_screen.load_experiment",
            new=mock.AsyncMock(
                return_value={
                    "display_name": "Alpha",
                    "run_columns": ["id"],
                    "runs_live": False,
                    "runs_list": [],
                    "run_groups": None,
                    "runs_view": None,
                }
            ),
        ),
    ):
        yield {"open_tables": open_tables}


def screens(app: BrowseApp) -> list[str]:
    return [type(screen).__name__ for screen in app.screen_stack[1:]]


def test_opens_on_the_experiment_list(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def drive() -> None:
        app = BrowseApp(CONFIG, None)
        async with app.run_test() as pilot:
            await pilot.pause()

            assert app.title == "project"
            assert screens(app) == ["ExperimentsScreen"]

    asyncio.run(drive())
    collaborators["open_tables"].assert_called_once_with(CONFIG, run_files=True)


def test_opens_a_named_experiment_over_the_list() -> None:
    async def drive() -> None:
        app = BrowseApp(CONFIG, "alpha")
        async with app.run_test() as pilot:
            await pilot.pause()

            assert screens(app) == ["ExperimentsScreen", "ExperimentScreen"]
            assert app.screen.experiment_name == "alpha"  # type: ignore[attr-defined]

    asyncio.run(drive())


def test_escape_goes_back_to_the_list() -> None:
    async def drive() -> None:
        app = BrowseApp(CONFIG, "alpha")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            assert screens(app) == ["ExperimentsScreen"]

    asyncio.run(drive())


def test_ctrl_c_quits_and_q_does_not() -> None:
    app = BrowseApp(CONFIG, None)

    async def drive() -> None:
        async with app.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()
            assert app.is_running

            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not app.is_running

    asyncio.run(drive())
    assert app.return_value is None


def test_shares_one_view_process_per_command_and_closes_them() -> None:
    async def drive() -> None:
        with mock.patch("labnotes.tui.browse_app.ViewProcess") as process:
            process.return_value.close = mock.AsyncMock()
            app = BrowseApp(CONFIG, None)
            async with app.run_test():
                first = app.view_request("go")
                second = app.view_request("go")

                assert first is second is process.return_value.request
                process.assert_called_once_with("go", CONFIG.root)
            process.return_value.close.assert_awaited_once_with()

    asyncio.run(drive())
