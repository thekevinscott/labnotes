import asyncio
from pathlib import Path
from unittest import mock

from labnotes.tui.view_switcher import ViewSwitcher


def test_add_views_mounts_ordered_panes_and_digit_bindings() -> None:
    host = mock.Mock()
    host.query_one.return_value.mount_all = mock.AsyncMock()
    specs = {"progress": "progress.py:Progress", "logs": "logs.py:Logs"}

    with mock.patch("labnotes.tui.view_switcher.ViewPane") as pane:
        asyncio.run(ViewSwitcher.add_views(host, specs, Path("/project")))

    assert pane.call_args_list == [
        mock.call("progress", "progress.py:Progress", Path("/project"), id="view-2"),
        mock.call("logs", "logs.py:Logs", Path("/project"), id="view-3"),
    ]
    host.query_one.return_value.mount_all.assert_awaited_once()
    assert host._bindings.bind.call_args_list == [
        mock.call("1", "show_view(1)", "runs"),
        mock.call("2", "show_view(2)", "progress"),
        mock.call("3", "show_view(3)", "logs"),
        mock.call("0", "show_view(1)"),
    ]


def test_no_extra_views_adds_no_digit_bindings() -> None:
    host = mock.Mock()
    asyncio.run(ViewSwitcher.add_views(host, {}, Path("/project")))
    host.query_one.assert_not_called()
    host._bindings.bind.assert_not_called()


def test_deliver_sends_the_experiment_to_every_pane() -> None:
    host = mock.Mock()
    panes = [mock.Mock(), mock.Mock()]
    host.query.return_value = panes
    experiment = mock.Mock()

    ViewSwitcher.deliver(host, experiment, frozenset({"a/stdout.log"}))

    for pane in panes:
        pane.deliver.assert_called_once_with(experiment, frozenset({"a/stdout.log"}))


def test_deliver_defaults_to_no_changed_paths() -> None:
    host = mock.Mock()
    pane = mock.Mock()
    host.query.return_value = [pane]

    ViewSwitcher.deliver(host, None)

    pane.deliver.assert_called_once_with(None, frozenset())


def test_show_view_remembers_focus_and_switches() -> None:
    host = mock.Mock(left={})
    switcher = host.query_one.return_value
    switcher.current = "view-1"

    ViewSwitcher.action_show_view(host, 2)

    assert host.left == {"view-1": host.focused}
    assert switcher.current == "view-2"
    host.call_after_refresh.assert_called_once_with(host.refocus, "view-2")


def test_show_view_remembers_nothing_without_focus() -> None:
    host = mock.Mock(left={}, focused=None)
    switcher = host.query_one.return_value
    switcher.current = "view-1"

    ViewSwitcher.action_show_view(host, 2)

    assert host.left == {}
    assert switcher.current == "view-2"


def test_show_view_remembers_nothing_before_any_view_is_current() -> None:
    host = mock.Mock(left={})
    host.query_one.return_value.current = None

    ViewSwitcher.action_show_view(host, 1)

    assert host.left == {}


def test_refocus_returns_to_the_remembered_widget() -> None:
    widget = mock.Mock(focusable=True)
    host = mock.Mock(left={"view-2": widget})

    ViewSwitcher.refocus(host, "view-2")

    widget.focus.assert_called_once_with()
    host.set_focus.assert_not_called()
    host.screen.focus_next.assert_not_called()


def test_refocus_moves_to_the_first_focusable_widget_otherwise() -> None:
    widget = mock.Mock(focusable=False)
    host = mock.Mock(left={"view-2": widget})

    ViewSwitcher.refocus(host, "view-2")

    widget.focus.assert_not_called()
    host.set_focus.assert_called_once_with(None)
    host.screen.focus_next.assert_called_once_with()


def test_refocus_with_nothing_remembered_moves_to_the_first_widget() -> None:
    host = mock.Mock(left={})

    ViewSwitcher.refocus(host, "view-3")

    host.set_focus.assert_called_once_with(None)
    host.screen.focus_next.assert_called_once_with()
