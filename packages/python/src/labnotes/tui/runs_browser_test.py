import asyncio
import dataclasses
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.runs_browser import Changed, Experiment, RunOutput, RunsBrowser

ROOT = Path("/p/project")
RUNS = {
    "alpha/runs/inv/first": {"id": "inv/first", "status": "passed"},
    "alpha/runs/lone": {"id": "lone", "status": "failed"},
}
EXPERIMENT = Experiment(
    ROOT,
    "alpha",
    RUNS,
    ("id",),
    ({"name": "inv", "flat": False}, {"name": "lone", "flat": True}),
)
COLUMNS = [{"key": "status", "label": ""}, {"key": "id", "label": "id"}]
CHANGED = Changed(EXPERIMENT)


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.runs_browser.invocation_columns", return_value=COLUMNS
        ) as invocation_columns,
        mock.patch(
            "labnotes.tui.runs_browser.invocation_rows",
            side_effect=lambda experiment, opened, columns, rows: [
                (key, [key]) for key in ["inv", *sorted(opened), "lone"]
            ],
        ) as invocation_rows,
        mock.patch("labnotes.tui.runs_browser.Static", return_value="status") as static,
        mock.patch(
            "labnotes.tui.runs_browser.RunsTable", return_value="runs table"
        ) as runs_table,
        mock.patch("labnotes.tui.runs_browser.fill_table") as fill_table,
        mock.patch("labnotes.tui.runs_browser.RunPanel") as run_panel,
    ):
        yield {
            "invocation_columns": invocation_columns,
            "invocation_rows": invocation_rows,
            "static": static,
            "runs_table": runs_table,
            "fill_table": fill_table,
            "run_panel": run_panel,
        }


@pytest.fixture
def table() -> mock.MagicMock:
    found = mock.MagicMock(cursor_row=1, row_count=2, display=True)
    found.coordinate_to_cell_key.return_value.row_key.value = "inv"
    return found


@pytest.fixture
def status() -> mock.MagicMock:
    return mock.MagicMock(display=False)


@pytest.fixture
def browser(
    table: mock.MagicMock,
    status: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> Iterator[RunsBrowser]:
    shown = RunsBrowser()

    def query_one(*query: object) -> object:
        if query[0] == "#view-status":
            return status
        if query[0] is collaborators["run_panel"]:
            return collaborators["run_panel"].return_value
        return table

    with (
        mock.patch.object(shown, "query_one", side_effect=query_one),
        mock.patch.object(shown, "run_worker"),
        mock.patch.object(shown, "mount", new=mock.AsyncMock()),
    ):
        yield shown


def filled(fill_table: mock.MagicMock) -> list[str]:
    [table, columns, rows] = fill_table.call_args.args
    return [key for key, _ in rows]


def test_shows_a_table_and_a_status_line(
    browser: RunsBrowser, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert list(browser.compose()) == ["runs table", "status"]
    collaborators["runs_table"].assert_called_once_with(id="runs", cursor_type="row")
    collaborators["static"].assert_called_once_with(id="view-status")


def test_binds_enter_and_escape() -> None:
    assert [
        (binding.key, binding.action, binding.description, binding.priority)  # type: ignore[union-attr]
        for binding in RunsBrowser.BINDINGS
    ] == [
        ("enter", "open_row", "Open", True),
        ("escape", "close_run", "Back", False),
    ]


def test_lists_the_runs_by_invocation(
    browser: RunsBrowser,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    browser.on_labnotes_changed(CHANGED)

    collaborators["invocation_columns"].assert_called_once_with(EXPERIMENT)
    collaborators["invocation_rows"].assert_called_once_with(
        EXPERIMENT, set(), COLUMNS, RUNS
    )
    collaborators["fill_table"].assert_called_once_with(
        table, ["", "id"], [("inv", ["inv"]), ("lone", ["lone"])]
    )
    assert browser.experiment == EXPERIMENT
    getattr(browser.run_worker, "assert_not_called")()


def test_hides_the_status_line_without_a_runs_view(
    browser: RunsBrowser, status: mock.MagicMock
) -> None:
    browser.on_labnotes_changed(CHANGED)

    status.update.assert_called_once_with("")
    assert status.display is False


VIEWED = Changed(dataclasses.replace(EXPERIMENT, runs_view="uv run view.py"))


@pytest.fixture
def process() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.tui.runs_browser.ViewProcess") as made:
        made.return_value.close = mock.AsyncMock()
        yield made


@pytest.fixture
def runs_view(process: mock.MagicMock) -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.tui.runs_browser.RunsView") as made:
        made.return_value.table.return_value = ([{"key": "m", "label": "M"}], {})
        made.return_value.status.return_value = ""
        made.return_value.next_request.return_value = None
        made.return_value.exchange = mock.AsyncMock(return_value=True)
        yield made


def test_starts_the_runs_view_once(
    browser: RunsBrowser, process: mock.MagicMock, runs_view: mock.MagicMock
) -> None:
    browser.on_labnotes_changed(VIEWED)
    browser.on_labnotes_changed(VIEWED)

    process.assert_called_once_with("uv run view.py", ROOT)
    runs_view.assert_called_once_with(process.return_value.request)
    assert (
        runs_view.return_value.update.call_args_list == [mock.call(COLUMNS, RUNS)] * 2
    )


def test_closes_the_runs_view_when_unmounted(
    browser: RunsBrowser, process: mock.MagicMock, runs_view: mock.MagicMock
) -> None:
    browser.on_labnotes_changed(VIEWED)

    asyncio.run(browser.on_unmount())

    process.return_value.close.assert_awaited_once_with()


def test_unmounts_without_a_runs_view(
    browser: RunsBrowser, process: mock.MagicMock
) -> None:
    browser.on_labnotes_changed(CHANGED)

    asyncio.run(browser.on_unmount())

    process.assert_not_called()


def test_draws_what_the_runs_view_shows(
    browser: RunsBrowser,
    collaborators: dict[str, mock.MagicMock],
    runs_view: mock.MagicMock,
) -> None:
    browser.on_labnotes_changed(VIEWED)

    collaborators["invocation_rows"].assert_called_once_with(
        VIEWED.experiment, set(), [{"key": "m", "label": "M"}], {}
    )
    assert collaborators["fill_table"].call_args.args[1] == ["M"]


def test_shows_what_the_runs_view_reports(
    browser: RunsBrowser,
    status: mock.MagicMock,
    runs_view: mock.MagicMock,
) -> None:
    runs_view.return_value.status.return_value = "runs view took 120 ms"

    browser.on_labnotes_changed(VIEWED)

    status.update.assert_called_once_with("runs view took 120 ms")
    assert status.display is True


def test_hides_the_status_line_while_a_run_is_open(
    browser: RunsBrowser, status: mock.MagicMock, runs_view: mock.MagicMock
) -> None:
    browser.view = runs_view.return_value
    runs_view.return_value.status.return_value = "runs view took 120 ms"
    browser.viewing = "lone"

    browser.show_status()

    status.update.assert_called_once_with("runs view took 120 ms")
    assert status.display is False


def test_asks_the_runs_view_when_it_has_a_request(
    browser: RunsBrowser, runs_view: mock.MagicMock
) -> None:
    runs_view.return_value.next_request.side_effect = [{"rows": {}}, None]
    with mock.patch.object(
        browser, "answer", new=mock.Mock(return_value="answering")
    ) as answer:
        browser.on_labnotes_changed(VIEWED)

    answer.assert_called_once_with(runs_view.return_value, {"rows": {}})
    getattr(browser.run_worker, "assert_called_once_with")(
        "answering", exit_on_error=False
    )


@pytest.mark.parametrize("changed", [True, False])
def test_redraws_only_when_the_answer_changed_and_asks_again(
    browser: RunsBrowser,
    status: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
    runs_view: mock.MagicMock,
    changed: bool,
) -> None:
    view = runs_view.return_value
    view.exchange.return_value = changed
    view.status.return_value = "runs view: broken"
    browser.view = view

    with mock.patch.object(browser, "ask") as ask:
        asyncio.run(browser.answer(view, {"rows": {}}))

    view.exchange.assert_awaited_once_with({"rows": {}})
    assert collaborators["fill_table"].called is changed
    status.update.assert_called_once_with("runs view: broken")
    ask.assert_called_once_with(view)


def test_marks_touched_files_and_asks(
    browser: RunsBrowser, collaborators: dict[str, mock.MagicMock]
) -> None:
    view = mock.Mock()
    browser.view = view
    paths = frozenset({"alpha/runs/lone/stdout.log", "alpha/runs/lone/stderr.log"})
    with mock.patch.object(browser, "ask") as ask:
        browser.on_labnotes_changed(Changed(CHANGED.experiment, paths))

    assert view.touch.call_args_list == [
        mock.call("alpha/runs/lone/stderr.log"),
        mock.call("alpha/runs/lone/stdout.log"),
    ]
    ask.assert_called_once_with(view)
    collaborators["fill_table"].assert_not_called()


def test_ignores_touched_files_without_a_runs_view(
    browser: RunsBrowser, collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch.object(browser, "ask") as ask:
        browser.on_labnotes_changed(
            Changed(CHANGED.experiment, frozenset({"alpha/runs/lone/stdout.log"}))
        )

    ask.assert_not_called()
    collaborators["fill_table"].assert_not_called()
    collaborators["invocation_columns"].assert_not_called()


def test_empties_when_the_experiment_is_removed(
    browser: RunsBrowser,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    browser.on_labnotes_changed(CHANGED)

    browser.on_labnotes_changed(Changed(None))

    collaborators["fill_table"].assert_called_with(table, [], [])
    assert collaborators["invocation_columns"].call_count == 1
    assert browser.experiment == EXPERIMENT


def test_keeps_opened_invocations_across_reloads(
    browser: RunsBrowser, collaborators: dict[str, mock.MagicMock]
) -> None:
    browser.on_labnotes_changed(CHANGED)
    asyncio.run(browser.action_open_row())

    browser.on_labnotes_changed(CHANGED)

    assert filled(collaborators["fill_table"]) == ["inv", "inv", "lone"]


def test_enter_opens_and_closes_an_invocation(
    browser: RunsBrowser, collaborators: dict[str, mock.MagicMock]
) -> None:
    browser.on_labnotes_changed(CHANGED)

    asyncio.run(browser.action_open_row())

    assert filled(collaborators["fill_table"]) == ["inv", "inv", "lone"]

    asyncio.run(browser.action_open_row())

    assert filled(collaborators["fill_table"]) == ["inv", "lone"]
    collaborators["run_panel"].assert_not_called()


@pytest.mark.parametrize(
    "key,folder", [("lone", "alpha/runs/lone"), ("inv/first", "alpha/runs/inv/first")]
)
def test_enter_opens_a_run_in_place_of_the_table(
    browser: RunsBrowser,
    table: mock.MagicMock,
    status: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
    key: str,
    folder: str,
) -> None:
    browser.on_labnotes_changed(CHANGED)
    collaborators["fill_table"].reset_mock()
    status.reset_mock()
    status.display = True
    table.coordinate_to_cell_key.return_value.row_key.value = key

    asyncio.run(browser.action_open_row())

    panel = collaborators["run_panel"]
    panel.assert_called_once_with(key, ROOT / folder)
    getattr(browser.mount, "assert_awaited_once_with")(panel.return_value)
    panel.return_value.query_one.assert_called_once_with(RunOutput)
    panel.return_value.query_one.return_value.focus.assert_called_once_with()
    assert browser.viewing == key
    assert table.display is False
    assert status.display is False
    collaborators["fill_table"].assert_not_called()
    assert browser.opened == set()


def test_enter_opens_runs_that_are_not_grouped(
    browser: RunsBrowser,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    browser.on_labnotes_changed(Changed(dataclasses.replace(EXPERIMENT, groups=None)))
    collaborators["fill_table"].reset_mock()
    table.coordinate_to_cell_key.return_value.row_key.value = "lone"

    asyncio.run(browser.action_open_row())

    collaborators["fill_table"].assert_not_called()
    collaborators["run_panel"].assert_called_once_with(
        "lone", Path("/p/project/alpha/runs/lone")
    )


def test_enter_does_nothing_without_rows(
    browser: RunsBrowser, table: mock.MagicMock
) -> None:
    table.row_count = 0

    asyncio.run(browser.action_open_row())

    table.coordinate_to_cell_key.assert_not_called()
    getattr(browser.mount, "assert_not_awaited")()


def test_escape_closes_the_run_and_shows_the_table(
    browser: RunsBrowser,
    table: mock.MagicMock,
    status: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
    runs_view: mock.MagicMock,
) -> None:
    browser.view = runs_view.return_value
    runs_view.return_value.status.return_value = "runs view: broken"
    browser.viewing = "lone"
    table.display = False

    browser.action_close_run()

    assert browser.viewing is None
    collaborators["run_panel"].return_value.remove.assert_called_once_with()
    assert table.display is True
    table.focus.assert_called_once_with()
    status.update.assert_called_once_with("runs view: broken")
    assert status.display is True


@pytest.mark.parametrize(
    "viewing,action,enabled",
    [
        (None, "open_row", True),
        (None, "close_run", False),
        ("lone", "open_row", False),
        ("lone", "close_run", True),
        (None, "other", True),
        ("lone", "other", True),
    ],
)
def test_enter_works_on_the_table_and_escape_on_a_run(
    browser: RunsBrowser, viewing: str | None, action: str, enabled: bool
) -> None:
    browser.viewing = viewing

    assert browser.check_action("".join(list(action)), ()) is enabled
