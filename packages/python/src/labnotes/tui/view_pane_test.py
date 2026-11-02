from pathlib import Path
from unittest import mock

from labnotes.tui.view_pane import ViewPane


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
