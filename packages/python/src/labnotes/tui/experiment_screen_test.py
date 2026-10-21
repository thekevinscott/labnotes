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
    "runs_list": [
        {"id": "inv/first", "folder": "alpha/runs/inv/first"},
        {"id": "lone", "folder": "alpha/runs/lone"},
    ],
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
        mock.patch("labnotes.tui.experiment_screen.fill_table") as fill_table,
        mock.patch(
            "labnotes.tui.experiment_screen.RunScreen", return_value="run screen"
        ) as run_screen,
        mock.patch(
            "labnotes.tui.experiment_screen.watch_rows", return_value="changes"
        ) as watch_rows,
        mock.patch(
            "labnotes.tui.experiment_screen.reload_on_change",
            new=mock.Mock(return_value="reloading"),
        ) as reload_on_change,
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
            "fill_table": fill_table,
            "run_screen": run_screen,
            "watch_rows": watch_rows,
            "reload_on_change": reload_on_change,
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


def filled(fill_table: mock.MagicMock) -> list[str]:
    [table, columns, rows] = fill_table.call_args.args
    return [key for key, _ in rows]


def test_shows_a_table_between_the_header_and_footer(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert list(screen.compose()) == ["header", "runs table", "footer"]
    collaborators["runs_table"].assert_called_once_with(id="runs", cursor_type="row")


def test_binds_enter_and_escape() -> None:
    assert [
        (binding.key, binding.action, binding.description, binding.priority)  # type: ignore[union-attr]
        for binding in ExperimentScreen.BINDINGS
    ] == [
        ("enter", "open_row", "Open", True),
        ("escape", "app.pop_screen", "Back", False),
    ]


def test_names_the_experiment_and_reloads_it_on_each_change(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    screen.on_mount()

    assert screen.sub_title == "alpha"
    collaborators["watch_rows"].assert_called_once_with(
        TABLES, {"runs", "experiment_configs"}, "alpha"
    )
    collaborators["reload_on_change"].assert_called_once_with("changes", screen.load)
    getattr(screen.run_worker, "assert_called_once_with")(
        "reloading", exit_on_error=False
    )


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
    collaborators["invocation_columns"].assert_called_once_with(LOADED)
    collaborators["invocation_rows"].assert_called_once_with(LOADED, set())
    collaborators["fill_table"].assert_called_once_with(
        table, ["", "id"], [("inv", ["inv"]), ("lone", ["lone"])]
    )


def test_rejects_an_unknown_experiment(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_experiment"].return_value = None

    with pytest.raises(ValueError, match="No experiment named alpha."):
        asyncio.run(screen.load())


def test_empties_when_the_experiment_is_removed(
    screen: ExperimentScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    asyncio.run(screen.load())
    collaborators["load_experiment"].return_value = None

    asyncio.run(screen.load())

    assert screen.sub_title == "alpha was removed."
    collaborators["fill_table"].assert_called_with(table, [], [])
    assert screen.experiment == LOADED


def test_keeps_opened_invocations_across_reloads(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    asyncio.run(screen.load())
    screen.action_open_row()

    asyncio.run(screen.load())

    assert filled(collaborators["fill_table"]) == ["inv", "inv", "lone"]


def test_enter_opens_and_closes_an_invocation(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    asyncio.run(screen.load())

    screen.action_open_row()

    assert filled(collaborators["fill_table"]) == ["inv", "inv", "lone"]

    screen.action_open_row()

    assert filled(collaborators["fill_table"]) == ["inv", "lone"]


@pytest.mark.parametrize(
    "key,folder", [("lone", "alpha/runs/lone"), ("inv/first", "alpha/runs/inv/first")]
)
def test_enter_opens_a_run_without_touching_the_rows(
    screen: ExperimentScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
    key: str,
    folder: str,
) -> None:
    asyncio.run(screen.load())
    collaborators["fill_table"].reset_mock()
    table.coordinate_to_cell_key.return_value.row_key.value = key

    screen.action_open_row()

    collaborators["run_screen"].assert_called_once_with(
        key, Path("/p/project") / folder
    )
    collaborators["app"].return_value.push_screen.assert_called_once_with("run screen")
    collaborators["fill_table"].assert_not_called()
    assert screen.opened == set()


def test_enter_on_an_invocation_opens_no_run(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    asyncio.run(screen.load())

    screen.action_open_row()

    collaborators["app"].return_value.push_screen.assert_not_called()


def test_enter_opens_runs_that_are_not_grouped(
    screen: ExperimentScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["load_experiment"].return_value = {**LOADED, "run_groups": None}
    asyncio.run(screen.load())
    collaborators["fill_table"].reset_mock()
    table.coordinate_to_cell_key.return_value.row_key.value = "lone"

    screen.action_open_row()

    collaborators["fill_table"].assert_not_called()
    collaborators["run_screen"].assert_called_once_with(
        "lone", Path("/p/project/alpha/runs/lone")
    )


def test_enter_does_nothing_without_rows(
    screen: ExperimentScreen, table: mock.MagicMock
) -> None:
    table.row_count = 0

    screen.action_open_row()

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
