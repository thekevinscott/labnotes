import asyncio
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.experiments_screen import ExperimentsScreen

CONFIG = mock.Mock()
TABLES = mock.Mock()
EXPERIMENTS = [
    {"name": "alpha", "last_run": "2026-10-17", "files": 2},
    {"name": "beta", "last_run": None, "files": 0},
]


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.experiments_screen.summarize_experiments",
            new=mock.AsyncMock(return_value=EXPERIMENTS),
        ) as summarize_experiments,
        mock.patch(
            "labnotes.tui.experiments_screen.ExperimentScreen"
        ) as experiment_screen,
        mock.patch(
            "labnotes.tui.experiments_screen.RunsTable", return_value="runs table"
        ) as runs_table,
        mock.patch("labnotes.tui.experiments_screen.Header", return_value="header"),
        mock.patch("labnotes.tui.experiments_screen.Footer", return_value="footer"),
        mock.patch.object(
            ExperimentsScreen, "app", new_callable=mock.PropertyMock
        ) as app,
    ):
        yield {
            "summarize_experiments": summarize_experiments,
            "experiment_screen": experiment_screen,
            "runs_table": runs_table,
            "app": app,
        }


@pytest.fixture
def table() -> mock.MagicMock:
    return mock.MagicMock()


@pytest.fixture
def screen(table: mock.MagicMock) -> Iterator[ExperimentsScreen]:
    shown = ExperimentsScreen(TABLES, CONFIG)
    with (
        mock.patch.object(shown, "query_one", return_value=table),
        mock.patch.object(shown, "run_worker"),
    ):
        yield shown


def test_shows_a_table_between_the_header_and_footer(
    screen: ExperimentsScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert list(screen.compose()) == ["header", "runs table", "footer"]
    collaborators["runs_table"].assert_called_once_with(
        id="experiments", cursor_type="row"
    )


def test_loads_the_experiments_on_mount(screen: ExperimentsScreen) -> None:
    screen.on_mount()

    [call] = getattr(screen.run_worker, "call_args_list")
    assert call.kwargs == {"exit_on_error": False}
    call.args[0].close()


def test_lists_the_experiments_with_the_table_columns(
    screen: ExperimentsScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    asyncio.run(screen.load())

    collaborators["summarize_experiments"].assert_awaited_once_with(TABLES)
    table.add_columns.assert_called_once_with("name", "last_run", "files")
    assert table.add_row.call_args_list == [
        mock.call("alpha", "2026-10-17", "2", key="alpha"),
        mock.call("beta", "", "0", key="beta"),
    ]


def test_says_when_there_are_no_experiments(
    screen: ExperimentsScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["summarize_experiments"].return_value = []

    asyncio.run(screen.load())

    assert screen.sub_title == "No experiments."
    table.add_columns.assert_not_called()


def test_enter_opens_the_selected_experiment(
    screen: ExperimentsScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    event = mock.Mock()
    event.row_key.value = "beta"

    screen.on_data_table_row_selected(event)

    collaborators["experiment_screen"].assert_called_once_with(TABLES, CONFIG, "beta")
    collaborators["app"].return_value.push_screen.assert_called_once_with(
        collaborators["experiment_screen"].return_value
    )


def test_exits_with_what_stopped_the_read(
    screen: ExperimentsScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    error = RuntimeError("bad scan")
    with mock.patch("labnotes.tui.experiments_screen.WorkerState") as states:
        screen.on_worker_state_changed(
            mock.Mock(state=states.RUNNING, worker=mock.Mock(error=None))
        )
        collaborators["app"].return_value.exit.assert_not_called()

        screen.on_worker_state_changed(
            mock.Mock(state=states.ERROR, worker=mock.Mock(error=error))
        )

    collaborators["app"].return_value.exit.assert_called_once_with(error)
