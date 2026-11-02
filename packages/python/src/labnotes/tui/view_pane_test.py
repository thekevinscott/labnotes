from pathlib import Path
from unittest import mock

from labnotes.tui.view_pane import ViewPane, failure


def test_delivers_changes_only_to_a_loaded_view() -> None:
    pane = ViewPane("progress", "views/progress.py:Progress", Path("/p"), id="view-2")
    shown = mock.Mock()

    pane.deliver(None)
    pane.view = shown
    pane.deliver(None, frozenset({"alpha/runs/a/stdout.log"}))

    shown.post_message.assert_called_once()
    [message] = shown.post_message.call_args.args
    assert message.experiment is None
    assert message.paths == {"alpha/runs/a/stdout.log"}


def test_failure_shows_a_plain_traceback() -> None:
    shown = failure("progress", ValueError("bad [bold]view"))

    assert "ValueError: bad [bold]view" in str(shown.content)
    assert shown.has_class("failure")


def test_compose_yields_a_loaded_view() -> None:
    pane = ViewPane("progress", "views/progress.py:Progress", Path("/p"), id="view-2")
    widget = mock.Mock()
    with (
        mock.patch("labnotes.tui.view_pane.load_view", return_value=widget),
        mock.patch("labnotes.tui.view_pane.guard_view", return_value=lambda: widget),
    ):
        assert list(pane.compose()) == [widget]

    assert pane.view is widget


def test_compose_yields_an_error_when_loading_fails() -> None:
    pane = ViewPane("progress", "views/progress.py:Progress", Path("/p"), id="view-2")
    with mock.patch(
        "labnotes.tui.view_pane.load_view", side_effect=ValueError("bad view")
    ):
        [shown] = list(pane.compose())

    assert "bad view" in str(getattr(shown, "content"))
    assert pane.view is None


def test_fail_replaces_a_loaded_view_once() -> None:
    pane = ViewPane("progress", "views/progress.py:Progress", Path("/p"), id="view-2")
    pane.view = mock.Mock()
    with (
        mock.patch.object(pane, "remove_children") as remove_children,
        mock.patch.object(pane, "mount") as mount,
    ):
        pane.fail(ValueError("bad view"))
        pane.fail(ValueError("again"))

    remove_children.assert_called_once_with()
    mount.assert_called_once()
    assert "bad view" in str(mount.call_args.args[0].content)
    assert pane.view is None
