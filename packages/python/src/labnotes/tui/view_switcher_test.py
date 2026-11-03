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
