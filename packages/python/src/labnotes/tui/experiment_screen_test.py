import asyncio
from collections.abc import AsyncIterator, Iterator
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
    "runs_view": None,
}
COLUMNS = [{"key": "status", "label": ""}, {"key": "id", "label": "id"}]
NATIVE = {"alpha/runs/lone": {"id": "lone"}}


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
            return_value=COLUMNS,
        ) as invocation_columns,
        mock.patch(
            "labnotes.tui.experiment_screen.native_rows", return_value=NATIVE
        ) as native_rows,
        mock.patch(
            "labnotes.tui.experiment_screen.invocation_rows",
            side_effect=lambda experiment, opened, columns, rows: [
                (key, [key]) for key in ["inv", *sorted(opened), "lone"]
            ],
        ) as invocation_rows,
        mock.patch(
            "labnotes.tui.experiment_screen.Static", return_value="status"
        ) as static,
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
            "native_rows": native_rows,
            "static": static,
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
def status() -> mock.MagicMock:
    return mock.MagicMock(display=False)


@pytest.fixture
def views() -> mock.MagicMock:
    return mock.MagicMock(return_value="request")


@pytest.fixture
def screen(
    table: mock.MagicMock, status: mock.MagicMock, views: mock.MagicMock
) -> Iterator[ExperimentScreen]:
    shown = ExperimentScreen(TABLES, CONFIG, "alpha", views)
    with (
        mock.patch.object(
            shown,
            "query_one",
            side_effect=lambda *query: status if query[0] == "#view-status" else table,
        ),
        mock.patch.object(shown, "run_worker"),
        mock.patch.object(shown, "watch_files", new=mock.Mock()),
    ):
        yield shown


def filled(fill_table: mock.MagicMock) -> list[str]:
    [table, columns, rows] = fill_table.call_args.args
    return [key for key, _ in rows]


def test_shows_a_table_between_the_header_and_footer(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert list(screen.compose()) == ["header", "runs table", "status", "footer"]
    collaborators["runs_table"].assert_called_once_with(id="runs", cursor_type="row")
    collaborators["static"].assert_called_once_with(id="view-status")


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
    collaborators["reload_on_change"].assert_called_once_with(
        "changes", screen.load, screen.stopped
    )
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
    collaborators["native_rows"].assert_called_once_with(LOADED)
    collaborators["invocation_rows"].assert_called_once_with(
        LOADED, set(), COLUMNS, NATIVE
    )
    collaborators["fill_table"].assert_called_once_with(
        table, ["", "id"], [("inv", ["inv"]), ("lone", ["lone"])]
    )
    getattr(screen.run_worker, "assert_not_called")()


def test_hides_the_status_line_without_a_runs_view(
    screen: ExperimentScreen, status: mock.MagicMock
) -> None:
    asyncio.run(screen.load())

    status.update.assert_called_once_with("")
    assert status.display is False


VIEWED = {**LOADED, "runs_view": "uv run view.py"}


@pytest.fixture
def runs_view() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.tui.experiment_screen.RunsView") as made:
        made.return_value.table.return_value = ([{"key": "m", "label": "M"}], {})
        made.return_value.status.return_value = ""
        made.return_value.next_request.return_value = None
        made.return_value.exchange = mock.AsyncMock(return_value=True)
        yield made


def test_starts_the_runs_view_once(
    screen: ExperimentScreen,
    collaborators: dict[str, mock.MagicMock],
    views: mock.MagicMock,
    runs_view: mock.MagicMock,
) -> None:
    collaborators["load_experiment"].return_value = VIEWED

    asyncio.run(screen.load())
    asyncio.run(screen.load())

    views.assert_called_once_with("uv run view.py")
    runs_view.assert_called_once_with("request")
    assert getattr(screen.run_worker, "call_count") == 1
    assert (
        runs_view.return_value.update.call_args_list == [mock.call(COLUMNS, NATIVE)] * 2
    )


def test_draws_what_the_runs_view_shows(
    screen: ExperimentScreen,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
    runs_view: mock.MagicMock,
) -> None:
    collaborators["load_experiment"].return_value = VIEWED

    asyncio.run(screen.load())

    collaborators["invocation_rows"].assert_called_once_with(
        VIEWED, set(), [{"key": "m", "label": "M"}], {}
    )
    assert collaborators["fill_table"].call_args.args[1] == ["M"]


def test_shows_what_the_runs_view_reports(
    screen: ExperimentScreen,
    status: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
    runs_view: mock.MagicMock,
) -> None:
    collaborators["load_experiment"].return_value = VIEWED
    runs_view.return_value.status.return_value = "runs view took 120 ms"

    asyncio.run(screen.load())

    status.update.assert_called_once_with("runs view took 120 ms")
    assert status.display is True


def test_asks_the_runs_view_when_it_has_a_request(
    screen: ExperimentScreen,
    collaborators: dict[str, mock.MagicMock],
    runs_view: mock.MagicMock,
) -> None:
    collaborators["load_experiment"].return_value = VIEWED
    runs_view.return_value.next_request.side_effect = [{"rows": {}}, None]
    with mock.patch.object(
        screen, "answer", new=mock.Mock(return_value="answering")
    ) as answer:
        asyncio.run(screen.load())

    answer.assert_called_once_with(runs_view.return_value, {"rows": {}})
    getattr(screen.run_worker, "assert_called_with")("answering", exit_on_error=False)


@pytest.mark.parametrize("changed", [True, False])
def test_redraws_only_when_the_answer_changed_and_asks_again(
    screen: ExperimentScreen,
    status: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
    runs_view: mock.MagicMock,
    changed: bool,
) -> None:
    view = runs_view.return_value
    view.exchange.return_value = changed
    view.status.return_value = "runs view: broken"
    screen.view = view

    with mock.patch.object(screen, "ask") as ask:
        asyncio.run(screen.answer(view, {"rows": {}}))

    view.exchange.assert_awaited_once_with({"rows": {}})
    assert collaborators["fill_table"].called is changed
    status.update.assert_called_once_with("runs view: broken")
    ask.assert_called_once_with(view)


def test_marks_touched_files_and_asks(
    screen: ExperimentScreen,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def changes() -> AsyncIterator[dict[str, object]]:
        yield {"path": "alpha/runs/lone/stderr.log"}

    collaborators["watch_rows"].return_value = changes()
    view = mock.Mock()
    with mock.patch.object(screen, "ask") as ask:
        asyncio.run(ExperimentScreen.watch_files(screen, view))

    collaborators["watch_rows"].assert_called_once_with(TABLES, {"run_files"}, "alpha")
    view.touch.assert_called_once_with("alpha/runs/lone/stderr.log")
    ask.assert_called_once_with(view)


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


def test_says_live_updates_stopped_after_the_name(screen: ExperimentScreen) -> None:
    screen.sub_title = "Alpha study"

    screen.stopped(OSError("watcher died"))

    assert screen.sub_title == "Alpha study · Live updates stopped: watcher died"
