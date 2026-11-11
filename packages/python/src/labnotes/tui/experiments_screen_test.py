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
        mock.patch("labnotes.tui.experiments_screen.fill_table") as fill_table,
        mock.patch(
            "labnotes.tui.experiments_screen.daemon_marker",
            new=mock.AsyncMock(return_value={"daemon": False, "running_cells": 0}),
        ) as marker,
        mock.patch(
            "labnotes.tui.experiments_screen.watch_rows", return_value="changes"
        ) as watch_rows,
        mock.patch(
            "labnotes.tui.experiments_screen.reload_on_change",
            new=mock.Mock(return_value="reloading"),
        ) as reload_on_change,
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
            "fill_table": fill_table,
            "marker": marker,
            "watch_rows": watch_rows,
            "reload_on_change": reload_on_change,
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
        mock.patch.object(shown, "set_interval"),
    ):
        yield shown


def test_shows_a_table_between_the_header_and_footer(
    screen: ExperimentsScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert list(screen.compose()) == ["header", "runs table", "footer"]
    collaborators["runs_table"].assert_called_once_with(
        id="experiments", cursor_type="row"
    )


def test_reloads_the_experiments_on_each_change(
    screen: ExperimentsScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    screen.on_mount()

    collaborators["watch_rows"].assert_called_once_with(
        TABLES, {"files", "runs", "experiment_configs"}
    )
    collaborators["reload_on_change"].assert_called_once_with(
        "changes", screen.load, screen.stopped
    )
    getattr(screen.run_worker, "assert_called_once_with")(
        "reloading", exit_on_error=False
    )
    getattr(screen.set_interval, "assert_called_once_with")(5, screen.refresh_daemons)


def test_refreshes_daemon_marker_without_file_change(screen: ExperimentsScreen) -> None:
    with mock.patch.object(screen, "load", new=mock.Mock(return_value="loading")):
        screen.refresh_daemons()
    getattr(screen.run_worker, "assert_called_once_with")(
        "loading", exit_on_error=False
    )


def test_lists_the_experiments_with_the_table_columns(
    screen: ExperimentsScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    screen.sub_title = "No experiments."

    asyncio.run(screen.load())

    collaborators["summarize_experiments"].assert_awaited_once_with(TABLES)
    assert screen.sub_title == ""
    collaborators["fill_table"].assert_called_once_with(
        table,
        ["name", "last_run", "files", "daemon", "running_cells"],
        [
            ("alpha", ["alpha", "2026-10-17", "2", "False", "0"]),
            ("beta", ["beta", "", "0", "False", "0"]),
        ],
    )
    assert collaborators["marker"].await_count == 2


def test_says_when_there_are_no_experiments(
    screen: ExperimentsScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["summarize_experiments"].return_value = []

    asyncio.run(screen.load())

    assert screen.sub_title == "No experiments."
    collaborators["fill_table"].assert_called_once_with(table, [], [])


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
        for state in (states.PENDING, states.RUNNING, states.CANCELLED, states.SUCCESS):
            screen.on_worker_state_changed(
                mock.Mock(state=state, worker=mock.Mock(error=None))
            )
        collaborators["app"].return_value.exit.assert_not_called()

        screen.on_worker_state_changed(
            mock.Mock(state=states.ERROR, worker=mock.Mock(error=error))
        )

    collaborators["app"].return_value.exit.assert_called_once_with(error)


def test_says_live_updates_stopped(screen: ExperimentsScreen) -> None:
    screen.stopped(OSError("watcher died"))

    assert screen.sub_title == "Live updates stopped: watcher died"
