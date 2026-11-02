import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.experiment_screen import ExperimentScreen
from labnotes.view.experiment import Experiment

ROOT = Path("/p/project")
CONFIG = mock.Mock(root=ROOT)
TABLES = mock.Mock()
LOADED = {"display_name": "Alpha study", "views": {}}
NATIVE = {"alpha/runs/lone": {"id": "lone"}}
SHOWN = Experiment(ROOT, "alpha", NATIVE)


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
            "labnotes.tui.experiment_screen.native_rows", return_value=NATIVE
        ) as native_rows,
        mock.patch(
            "labnotes.tui.experiment_screen.watch_rows", return_value="changes"
        ) as watch_rows,
        mock.patch(
            "labnotes.tui.experiment_screen.reload_on_change",
            new=mock.Mock(return_value="reloading"),
        ) as reload_on_change,
        mock.patch("labnotes.tui.experiment_screen.Header", return_value="header"),
        mock.patch("labnotes.tui.experiment_screen.Footer", return_value="footer"),
        mock.patch(
            "labnotes.tui.experiment_screen.ViewPane",
            side_effect=lambda name, spec, root, id: mock.Mock(
                view_name=name, source=spec, root=root, id=id
            ),
        ) as view_pane,
        mock.patch(
            "labnotes.tui.experiment_screen.ContentSwitcher"
        ) as content_switcher,
        mock.patch.object(
            ExperimentScreen, "app", new_callable=mock.PropertyMock
        ) as app,
    ):
        yield {
            "load_experiment": load_experiment,
            "native_rows": native_rows,
            "watch_rows": watch_rows,
            "reload_on_change": reload_on_change,
            "view_pane": view_pane,
            "content_switcher": content_switcher,
            "app": app,
        }


@pytest.fixture
def switcher() -> mock.MagicMock:
    found = mock.MagicMock(current="".join(["view-", "1"]))
    found.mount_all = mock.AsyncMock()
    return found


@pytest.fixture
def panes() -> list[mock.MagicMock]:
    return [mock.Mock(), mock.Mock()]


@pytest.fixture
def views() -> mock.MagicMock:
    return mock.MagicMock(return_value="request")


@pytest.fixture
def screen(
    switcher: mock.MagicMock, panes: list[mock.MagicMock], views: mock.MagicMock
) -> Iterator[ExperimentScreen]:
    shown = ExperimentScreen(TABLES, CONFIG, "alpha", views)
    with (
        mock.patch.object(shown, "query_one", return_value=switcher),
        mock.patch.object(shown, "query", return_value=panes),
        mock.patch.object(shown, "run_worker"),
        mock.patch.object(shown, "refresh_bindings"),
        mock.patch.object(shown, "call_after_refresh"),
        mock.patch.object(shown, "watch_files", new=mock.Mock(return_value="files")),
    ):
        yield shown


def test_shows_the_built_in_view_between_the_header_and_footer(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    shown = list(screen.compose())

    assert shown[0] == "header"
    assert shown[2] == "footer"
    pane: Any = shown[1]
    assert (pane.view_name, pane.source, pane.root, pane.id) == (
        "runs",
        "labnotes.tui.runs_browser:RunsBrowser",
        ROOT,
        "view-1",
    )
    collaborators["content_switcher"].assert_called_once_with(initial="view-1")


def test_binds_escape_and_zero() -> None:
    assert [
        (binding.key, binding.action, binding.description, binding.show)  # type: ignore[union-attr]
        for binding in ExperimentScreen.BINDINGS
    ] == [
        ("escape", "back", "Back", True),
        ("0", "show_view(1)", "", False),
    ]


def test_keeps_what_the_app_passes(
    screen: ExperimentScreen, views: mock.MagicMock
) -> None:
    assert screen.tables is TABLES
    assert screen.config is CONFIG
    assert screen.experiment_name == "alpha"
    assert screen.views is views
    assert screen.experiment == {}
    assert screen.shown is None
    assert screen.left == {}


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
    assert getattr(screen.run_worker, "call_args_list") == [
        mock.call("reloading", exit_on_error=False),
        mock.call("files", exit_on_error=False),
    ]


def test_hands_each_view_the_experiment(
    screen: ExperimentScreen,
    panes: list[mock.MagicMock],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    asyncio.run(screen.load())

    collaborators["load_experiment"].assert_awaited_once_with(
        TABLES, ROOT, "alpha", "no params"
    )
    collaborators["native_rows"].assert_called_once_with(LOADED)
    assert screen.sub_title == "Alpha study"
    assert screen.experiment == LOADED
    assert screen.shown == SHOWN
    for pane in panes:
        pane.deliver.assert_called_once_with(SHOWN, frozenset())


def test_rejects_an_unknown_experiment(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_experiment"].return_value = None

    with pytest.raises(ValueError, match="No experiment named alpha."):
        asyncio.run(screen.load())


def test_tells_each_view_the_experiment_was_removed(
    screen: ExperimentScreen,
    panes: list[mock.MagicMock],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    asyncio.run(screen.load())
    collaborators["load_experiment"].return_value = None

    asyncio.run(screen.load())

    assert screen.sub_title == "alpha was removed."
    assert screen.shown is None
    assert screen.experiment == LOADED
    for pane in panes:
        pane.deliver.assert_called_with(None, frozenset())


def test_shows_the_built_in_view_key_without_custom_views(
    screen: ExperimentScreen, switcher: mock.MagicMock
) -> None:
    asyncio.run(screen.load())

    switcher.mount_all.assert_not_awaited()
    getattr(screen.refresh_bindings, "assert_called_once_with")()
    assert screen._bindings.key_to_bindings["1"][0].description == "runs"


def test_adds_hidden_views_and_a_key_for_each_once(
    screen: ExperimentScreen,
    switcher: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    specs = {f"v{number}": f"views/v{number}.py:V" for number in range(9)}
    collaborators["load_experiment"].return_value = {**LOADED, "views": specs}

    asyncio.run(screen.load())
    asyncio.run(screen.load())

    [panes] = switcher.mount_all.await_args.args
    switcher.mount_all.assert_awaited_once()
    assert [(pane.view_name, pane.source, pane.root, pane.id) for pane in panes] == [
        (f"v{number}", f"views/v{number}.py:V", ROOT, f"view-{number + 2}")
        for number in range(8)
    ]
    assert all(pane.display is False for pane in panes)
    keys = {
        key: [(binding.action, binding.description, binding.show) for binding in found]
        for key, found in screen._bindings.key_to_bindings.items()
    }
    assert keys["1"] == [("show_view(1)", "runs", True)]
    assert keys["2"] == [("show_view(2)", "v0", True)]
    assert keys["9"] == [("show_view(9)", "v7", True)]
    assert keys["0"] == [("show_view(1)", "", False)]
    getattr(screen.refresh_bindings, "assert_called_once_with")()


def test_hands_each_view_the_files_that_changed(
    screen: ExperimentScreen,
    panes: list[mock.MagicMock],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def changes() -> AsyncIterator[dict[str, object]]:
        yield {"path": "alpha/runs/lone/stderr.log"}
        screen.shown = SHOWN
        yield {"path": "alpha/runs/lone/stdout.log"}

    collaborators["watch_rows"].return_value = changes()

    asyncio.run(ExperimentScreen.watch_files(screen))

    collaborators["watch_rows"].assert_called_once_with(TABLES, {"run_files"}, "alpha")
    for pane in panes:
        pane.deliver.assert_called_once_with(
            SHOWN, frozenset({"alpha/runs/lone/stdout.log"})
        )


def test_switches_views_and_restores_focus_after(
    screen: ExperimentScreen, switcher: mock.MagicMock
) -> None:
    focused = mock.Mock()
    with mock.patch.object(
        ExperimentScreen, "focused", new_callable=mock.PropertyMock
    ) as current:
        current.return_value = focused
        screen.action_show_view(3)

    assert switcher.current == "view-3"
    assert screen.left == {"view-1": focused}
    getattr(screen.call_after_refresh, "assert_called_once_with")(
        screen.refocus, "view-3"
    )


def test_switching_without_focus_remembers_nothing(
    screen: ExperimentScreen, switcher: mock.MagicMock
) -> None:
    with mock.patch.object(
        ExperimentScreen, "focused", new_callable=mock.PropertyMock, return_value=None
    ):
        screen.action_show_view(2)

    assert switcher.current == "view-2"
    assert screen.left == {}


def test_refocuses_what_had_focus(screen: ExperimentScreen) -> None:
    widget = mock.Mock(focusable=True)
    screen.left = {"view-2": widget}
    with (
        mock.patch.object(screen, "set_focus") as set_focus,
        mock.patch.object(screen, "focus_next") as focus_next,
    ):
        screen.refocus("view-2")

    widget.focus.assert_called_once_with()
    set_focus.assert_not_called()
    focus_next.assert_not_called()


@pytest.mark.parametrize("left", [{}, {"view-2": mock.Mock(focusable=False)}])
def test_focuses_the_first_widget_otherwise(
    screen: ExperimentScreen, left: dict[str, Any]
) -> None:
    screen.left = left
    with (
        mock.patch.object(screen, "set_focus") as set_focus,
        mock.patch.object(screen, "focus_next") as focus_next,
    ):
        screen.refocus("view-2")

    set_focus.assert_called_once_with(None)
    focus_next.assert_called_once_with()
    for widget in left.values():
        widget.focus.assert_not_called()


def test_escape_leaves_from_the_built_in_view(
    screen: ExperimentScreen, collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch.object(screen, "action_show_view") as show_view:
        screen.action_back()

    collaborators["app"].return_value.pop_screen.assert_called_once_with()
    show_view.assert_not_called()


def test_escape_goes_back_to_the_built_in_view(
    screen: ExperimentScreen,
    switcher: mock.MagicMock,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    switcher.current = "view-2"
    with mock.patch.object(screen, "action_show_view") as show_view:
        screen.action_back()

    show_view.assert_called_once_with(1)
    collaborators["app"].return_value.pop_screen.assert_not_called()


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
