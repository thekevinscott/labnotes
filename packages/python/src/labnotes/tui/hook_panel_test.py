from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.hook_panel import HookPanel


@pytest.fixture
def parts() -> dict[str, mock.Mock]:
    return {"header": mock.Mock(), "output": mock.Mock()}


@pytest.fixture
def panel(parts: dict[str, mock.Mock]) -> HookPanel:
    widget = HookPanel("setup")
    lookup = {".hook-header": parts["header"]}
    widget.query_one = lambda selector, *_: lookup.get(selector, parts["output"])  # type: ignore[method-assign,assignment]
    return widget


def shown(header: mock.Mock) -> str:
    return str(header.update.call_args.args[0])


def test_waits_until_the_hook_starts(
    panel: HookPanel, parts: dict[str, mock.Mock]
) -> None:
    panel.tick()
    assert panel.state == "waiting"
    assert shown(parts["header"]) == "setup: waiting"


def test_shows_the_elapsed_time_and_outcome(
    panel: HookPanel, parts: dict[str, mock.Mock], tmp_path: Path
) -> None:
    panel.start(tmp_path, 100.0)
    assert panel.state == "running"
    panel.end(None, 250.0)
    assert panel.state == "passed"
    assert shown(parts["header"]) == "setup: ✓  2m 30s"


def test_shows_the_error_of_a_failed_hook(
    panel: HookPanel, parts: dict[str, mock.Mock], tmp_path: Path
) -> None:
    panel.start(tmp_path, 100.0)
    panel.end("setup command up exited 3", 102.0)
    assert panel.state == "failed"
    assert shown(parts["header"]) == "setup: ✗ setup command up exited 3  2s"
    assert parts["header"].update.call_args.args[0].style == "red"


def test_shows_running_time_while_the_hook_runs(
    panel: HookPanel, parts: dict[str, mock.Mock], tmp_path: Path
) -> None:
    with mock.patch("labnotes.tui.hook_panel.time.monotonic", return_value=250.0):
        panel.start(tmp_path, 100.0)
    assert shown(parts["header"]) == "setup: running  2m 30s"


def test_follows_the_hooks_log_folder(
    panel: HookPanel, parts: dict[str, mock.Mock], tmp_path: Path
) -> None:
    panel.follow()
    parts["output"].follow.assert_not_called()
    panel.start(tmp_path, 100.0)
    panel.follow()
    parts["output"].follow.assert_called_once_with(tmp_path)


def test_end_before_start_leaves_no_elapsed_time(panel: HookPanel) -> None:
    panel.end(None, 5.0)
    assert (panel.took, panel.state) == (None, "waiting")


def test_shows_the_waiting_header_without_markup() -> None:
    header: Any
    header, _ = HookPanel("setup").compose()
    header.update("[b]setup")
    assert str(header.render()) == "[b]setup"
