import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.experiment_screen import ExperimentScreen

CONFIG = mock.Mock(root=Path("/p/project"), mode="matrix")
TABLES = mock.Mock()
LOADED = {
    "display_name": "Alpha study",
    "run_groups": [{"name": "inv", "flat": False}, {"name": "lone", "flat": True}],
}


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.experiment_screen.load_experiment",
            new=mock.AsyncMock(return_value=LOADED),
        ) as load_experiment,
        mock.patch(
            "labnotes.tui.experiment_screen.QueryParams", return_value="no params"
        ),
        mock.patch(
            "labnotes.tui.experiment_screen.invocation_columns",
            return_value=["", "id"],
        ) as invocation_columns,
        mock.patch(
            "labnotes.tui.experiment_screen.invocation_rows",
            side_effect=lambda experiment, opened: [
                (key, [key]) for key in ["inv", *sorted(opened), "lone"]
            ],
        ) as invocation_rows,
        mock.patch(
            "labnotes.tui.experiment_screen.RunsTable", return_value="runs table"
        ) as runs_table,
        mock.patch("labnotes.tui.experiment_screen.Header", return_value="header"),
        mock.patch("labnotes.tui.experiment_screen.Footer", return_value="footer"),
        mock.patch.object(
            ExperimentScreen, "app", new_callable=mock.PropertyMock
        ) as app,
    ):
        yield {
            "load_experiment": load_experiment,
            "invocation_columns": invocation_columns,
            "invocation_rows": invocation_rows,
            "runs_table": runs_table,
            "app": app,
        }


@pytest.fixture
def table() -> mock.MagicMock:
    found = mock.MagicMock(cursor_row=1, row_count=2)
    found.coordinate_to_cell_key.return_value.row_key.value = "inv"
    return found


@pytest.fixture
def screen(table: mock.MagicMock) -> Iterator[ExperimentScreen]:
    shown = ExperimentScreen(TABLES, CONFIG, "alpha")
    with (
        mock.patch.object(shown, "query_one", return_value=table),
        mock.patch.object(shown, "run_worker"),
    ):
        yield shown


def added(table: mock.MagicMock) -> list[tuple[object, ...]]:
    return [(call.kwargs["key"], *call.args) for call in table.add_row.call_args_list]


def test_shows_a_table_between_the_header_and_footer(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert list(screen.compose()) == ["header", "runs table", "footer"]
    collaborators["runs_table"].assert_called_once_with(id="runs", cursor_type="row")


def test_binds_space_and_escape() -> None:
    assert [
        (binding.key, binding.action, binding.description)  # type: ignore[union-attr]
        for binding in ExperimentScreen.BINDINGS
    ] == [
        ("space", "open_invocation", "Open invocation"),
        ("escape", "app.pop_screen", "Back"),
    ]


def test_names_the_experiment_and_loads_it(screen: ExperimentScreen) -> None:
    screen.on_mount()

    assert screen.sub_title == "alpha"
    [call] = getattr(screen.run_worker, "call_args_list")
    assert call.kwargs == {"exit_on_error": False}
    call.args[0].close()


def test_lists_the_runs_by_invocation(
    screen: ExperimentScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    asyncio.run(screen.load())

    collaborators["load_experiment"].assert_awaited_once_with(
        TABLES, CONFIG.root, "matrix", "alpha", "no params"
    )
    assert screen.sub_title == "Alpha study"
    table.add_columns.assert_called_once_with("", "id")
    collaborators["invocation_columns"].assert_called_once_with(LOADED)
    collaborators["invocation_rows"].assert_called_once_with(LOADED, set())
    table.clear.assert_called_once_with()
    assert added(table) == [("inv", "inv"), ("lone", "lone")]
    table.move_cursor.assert_called_once_with(row=1)


def test_rejects_an_unknown_experiment(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_experiment"].return_value = None

    with pytest.raises(ValueError, match="No experiment named alpha."):
        asyncio.run(screen.load())


def test_space_opens_and_closes_an_invocation(
    screen: ExperimentScreen, table: mock.MagicMock
) -> None:
    asyncio.run(screen.load())
    table.reset_mock()

    screen.action_open_invocation()

    assert added(table) == [("inv", "inv"), ("inv", "inv"), ("lone", "lone")]

    table.reset_mock()
    screen.action_open_invocation()

    assert added(table) == [("inv", "inv"), ("lone", "lone")]


def test_space_leaves_a_lone_run_alone(
    screen: ExperimentScreen, table: mock.MagicMock
) -> None:
    asyncio.run(screen.load())
    table.reset_mock()
    table.coordinate_to_cell_key.return_value.row_key.value = "lone"

    screen.action_open_invocation()

    table.add_row.assert_not_called()
    assert screen.opened == set()


def test_space_ignores_runs_that_are_not_grouped(
    screen: ExperimentScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["load_experiment"].return_value = {**LOADED, "run_groups": None}
    asyncio.run(screen.load())
    table.reset_mock()

    screen.action_open_invocation()

    table.add_row.assert_not_called()


def test_space_does_nothing_without_rows(
    screen: ExperimentScreen, table: mock.MagicMock
) -> None:
    table.row_count = 0

    screen.action_open_invocation()

    table.coordinate_to_cell_key.assert_not_called()


def test_exits_with_what_stopped_the_load(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    error = ValueError("broken")
    with mock.patch("labnotes.tui.experiment_screen.WorkerState") as states:
        screen.on_worker_state_changed(
            mock.Mock(state=states.RUNNING, worker=mock.Mock(error=None))
        )
        collaborators["app"].return_value.exit.assert_not_called()

        screen.on_worker_state_changed(
            mock.Mock(state=states.ERROR, worker=mock.Mock(error=error))
        )

    collaborators["app"].return_value.exit.assert_called_once_with(error)
