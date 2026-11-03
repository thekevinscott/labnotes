from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.run_panel import RunPanel

FOLDER = Path("/p/project/alpha/runs/first")


@pytest.fixture(autouse=True)
def widgets() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.tui.run_panel.Static", return_value="run id") as static,
        mock.patch(
            "labnotes.tui.run_panel.RunOutput", return_value="output"
        ) as run_output,
        mock.patch("labnotes.tui.run_panel.LogBlocks", return_value="blocks") as blocks,
    ):
        yield {"static": static, "output": run_output, "blocks": blocks}


@pytest.fixture
def output() -> mock.MagicMock:
    return mock.MagicMock()


@pytest.fixture
def panel(output: mock.MagicMock) -> Iterator[RunPanel]:
    shown = RunPanel("20261017-000000/first", FOLDER)
    with (
        mock.patch.object(shown, "query_one", return_value=output),
        mock.patch.object(shown, "set_interval"),
    ):
        yield shown


def test_shows_the_run_id_then_log_blocks_then_the_output(
    panel: RunPanel, widgets: dict[str, mock.MagicMock]
) -> None:
    assert list(panel.compose()) == ["run id", "blocks", "output"]
    widgets["static"].assert_called_once_with(
        "20261017-000000/first", id="run-id", markup=False
    )
    widgets["output"].assert_called_once_with(id="output")
    widgets["blocks"].assert_called_once_with(id="blocks")


def test_follows_the_run_folder(
    panel: RunPanel, output: mock.MagicMock, widgets: dict[str, mock.MagicMock]
) -> None:
    panel.on_mount()

    assert [call.args for call in getattr(panel.query_one, "call_args_list")] == [
        (widgets["blocks"],),
        (widgets["output"],),
    ]
    assert output.follow.call_args_list == [mock.call(FOLDER), mock.call(FOLDER)]
    getattr(panel.set_interval, "assert_called_once_with")(0.25, panel.follow)
