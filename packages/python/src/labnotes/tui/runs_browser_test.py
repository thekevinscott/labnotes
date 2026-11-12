import asyncio
import dataclasses
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.runs_browser import Changed, Experiment, RunOutput, RunsBrowser

ROOT = Path("/p/project")
RUNS = (
    {"id": "inv/first", "folder": "alpha/runs/inv/first", "status": "passed"},
    {"id": "lone", "folder": "alpha/runs/lone", "status": "failed"},
)
BY_FOLDER = {str(run["folder"]): run for run in RUNS}
EXPERIMENT = Experiment(ROOT, "alpha", RUNS, {"command": "go"})
COLUMNS = [{"key": "status", "label": ""}, {"key": "id", "label": "id"}]
CHANGED = Changed(EXPERIMENT)


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.runs_browser.table_columns", return_value=COLUMNS
        ) as table_columns,
        mock.patch(
            "labnotes.tui.runs_browser.table_rows",
            side_effect=lambda runs, columns, rows: [
                (str(run["folder"]), [run["id"]]) for run in runs
            ],
        ) as table_rows,
        mock.patch("labnotes.tui.runs_browser.Static", return_value="status") as static,
        mock.patch(
            "labnotes.tui.runs_browser.RunsTable", return_value="runs table"
        ) as runs_table,
        mock.patch("labnotes.tui.runs_browser.fill_table") as fill_table,
        mock.patch("labnotes.tui.runs_browser.RunPanel") as run_panel,
        mock.patch(
            "labnotes.tui.runs_browser.runs_view_command",
            side_effect=lambda config: config.get("views", {}).get("runs"),
        ) as runs_view_command,
    ):
        yield {
            "table_columns": table_columns,
            "table_rows": table_rows,
            "static": static,
            "runs_table": runs_table,
            "fill_table": fill_table,
            "run_panel": run_panel,
            "runs_view_command": runs_view_command,
        }


@pytest.fixture
def table() -> mock.MagicMock:
    found = mock.MagicMock(cursor_row=1, row_count=2, display=True)
    found.coordinate_to_cell_key.return_value.row_key.value = "alpha/runs/lone"
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
        ("r", "restart_run", "Restart", True),
    ]


@pytest.mark.parametrize(
    "row,claim,expected,launched",
    [
        ({"ended": None, "exit_code": 1}, None, "has not failed", False),
        ({"ended": "now", "exit_code": 0}, None, "has not failed", False),
        ({"ended": "now", "exit_code": 0, "error": "broken"}, 42, "Restarting", True),
        ({"ended": "now", "exit_code": 1}, None, "held by another run", False),
        ({"ended": "now", "exit_code": 1}, 42, "Restarting", True),
        ({"ended": "now", "exit_code": -9}, 42, "Restarting", True),
    ],
)
def test_restart_key_checks_selected_run(
    browser: RunsBrowser,
    table: mock.MagicMock,
    status: mock.MagicMock,
    row: dict[str, object],
    claim: int | None,
    expected: str,
    launched: bool,
) -> None:
    browser.experiment = Experiment(ROOT, "alpha", ({**RUNS[1], **row},))
    with (
        mock.patch(
            "labnotes.tui.runs_browser.claim_run", return_value=claim
        ) as claim_run,
        mock.patch("labnotes.tui.runs_browser.os.close") as close,
        mock.patch.object(
            browser, "restart", new=mock.Mock(return_value=mock.sentinel.work)
        ) as restart,
    ):
        browser.action_restart_run()

    assert expected in browser.restart_status
    status.update.assert_called_with(browser.restart_status)
    if row.get("ended") is None or (row.get("exit_code") == 0 and not row.get("error")):
        claim_run.assert_not_called()
    else:
        claim_run.assert_called_once_with(ROOT / "alpha/runs/lone")
    assert close.called is launched
    assert restart.called is launched
    assert getattr(browser.run_worker, "called") is launched
    if launched:
        getattr(browser.run_worker, "assert_called_once_with")(
            mock.sentinel.work, exit_on_error=False
        )


def test_restart_action_uses_value_equality_and_checks_view_state(
    browser: RunsBrowser,
) -> None:
    equal = "".join(["restart", "_run"])
    expected = "restart_run"
    assert equal == expected and equal is not expected
    assert browser.check_action(equal, ()) is True
    browser.viewing = "lone"
    assert browser.check_action(equal, ()) is False
    assert browser.check_action("zzzz", ()) is True


def test_restart_selects_exact_folder_among_neighbors(
    browser: RunsBrowser, table: mock.MagicMock
) -> None:
    target = "".join(["alpha/runs/", "lone"])
    expected = "alpha/runs/lone"
    assert target == expected and target is not expected
    table.coordinate_to_cell_key.return_value.row_key.value = target
    browser.experiment = Experiment(
        ROOT,
        "alpha",
        (
            {
                "id": "before",
                "folder": "alpha/runs/aaaa",
                "ended": "now",
                "exit_code": 0,
            },
            {
                "id": "after",
                "folder": "alpha/runs/zzzz",
                "ended": "now",
                "exit_code": 0,
            },
            {"id": "lone", "folder": "alpha/runs/lone", "ended": "now", "exit_code": 1},
        ),
    )
    with (
        mock.patch("labnotes.tui.runs_browser.claim_run", return_value=42),
        mock.patch("labnotes.tui.runs_browser.os.close"),
        mock.patch.object(
            browser, "restart", new=mock.Mock(return_value=mock.sentinel.work)
        ) as restart,
    ):
        browser.action_restart_run()
    restart.assert_called_once_with("lone")


def test_restart_key_ignores_an_empty_table(
    browser: RunsBrowser, table: mock.MagicMock
) -> None:
    table.row_count = 0
    browser.action_restart_run()
    getattr(browser.run_worker, "assert_not_called")()


@pytest.mark.parametrize(
    "reply,expected",
    [
        ({"ok": True, "batch": "b1"}, "Restarted lone"),
        ({"ok": False, "error": "locked"}, "Could not restart lone: locked"),
    ],
)
def test_restart_worker_reports_daemon_reply(
    browser: RunsBrowser,
    status: mock.MagicMock,
    reply: dict[str, object],
    expected: str,
) -> None:
    app = mock.Mock(config=mock.Mock(path=Path("/p/project/.labnotes.toml")))
    browser.experiment = Experiment(ROOT, "alpha", ())
    with (
        mock.patch.object(
            type(browser), "app", new_callable=mock.PropertyMock, return_value=app
        ),
        mock.patch(
            "labnotes.tui.runs_browser.ensure_daemon", new=mock.AsyncMock()
        ) as ensure,
        mock.patch(
            "labnotes.tui.runs_browser.daemon_command", return_value=reply
        ) as command,
        mock.patch(
            "labnotes.tui.runs_browser.restart_request",
            return_value=mock.sentinel.request,
        ) as request,
    ):
        asyncio.run(browser.restart("lone"))
    assert expected in browser.restart_status
    status.update.assert_called_with(browser.restart_status)
    ensure.assert_awaited_once_with(app.config, "alpha")
    request.assert_called_once_with("lone", None)
    command.assert_called_once_with(app.config, "alpha", mock.sentinel.request)


def test_lists_every_run_flat(
    browser: RunsBrowser,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    browser.on_labnotes_changed(CHANGED)

    collaborators["table_columns"].assert_called_once_with({"command": "go"})
    collaborators["table_rows"].assert_called_once_with(RUNS, COLUMNS, BY_FOLDER)
    collaborators["fill_table"].assert_called_once_with(
        table,
        ["", "id"],
        [("alpha/runs/inv/first", ["inv/first"]), ("alpha/runs/lone", ["lone"])],
    )
    assert browser.experiment == EXPERIMENT
    getattr(browser.run_worker, "assert_not_called")()


def test_hides_the_status_line_without_a_runs_view(
    browser: RunsBrowser, status: mock.MagicMock
) -> None:
    browser.on_labnotes_changed(CHANGED)

    status.update.assert_called_once_with("")
    assert status.display is False


VIEWED = Changed(
    dataclasses.replace(EXPERIMENT, config={"views": {"runs": "uv run view.py"}})
)


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
    browser: RunsBrowser,
    process: mock.MagicMock,
    runs_view: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    browser.on_labnotes_changed(VIEWED)
    browser.on_labnotes_changed(VIEWED)

    collaborators["runs_view_command"].assert_called_with(
        {"views": {"runs": "uv run view.py"}}
    )
    process.assert_called_once_with("uv run view.py", ROOT)
    runs_view.assert_called_once_with(process.return_value.request)
    assert (
        runs_view.return_value.update.call_args_list
        == [mock.call(COLUMNS, BY_FOLDER)] * 2
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

    collaborators["table_rows"].assert_called_once_with(
        RUNS, [{"key": "m", "label": "M"}], {}
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
    collaborators["table_columns"].assert_not_called()


def test_empties_when_the_experiment_is_removed(
    browser: RunsBrowser,
    table: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    browser.on_labnotes_changed(CHANGED)

    browser.on_labnotes_changed(Changed(None))

    collaborators["fill_table"].assert_called_with(table, [], [])
    assert collaborators["table_columns"].call_count == 1
    assert browser.experiment == EXPERIMENT


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
    table.coordinate_to_cell_key.return_value.row_key.value = folder

    asyncio.run(browser.action_open_row())

    panel = collaborators["run_panel"]
    panel.assert_called_once_with(key, ROOT / folder)
    getattr(browser.mount, "assert_awaited_once_with")(panel.return_value)
    panel.return_value.query_one.assert_called_once_with(RunOutput)
    panel.return_value.query_one.return_value.focus.assert_called_once_with()
    assert browser.viewing == folder
    assert table.display is False
    assert status.display is False
    collaborators["fill_table"].assert_not_called()


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
        (None, "a", True),
        ("lone", "other", True),
    ],
)
def test_enter_works_on_the_table_and_escape_on_a_run(
    browser: RunsBrowser, viewing: str | None, action: str, enabled: bool
) -> None:
    browser.viewing = viewing

    assert browser.check_action("".join(list(action)), ()) is enabled
