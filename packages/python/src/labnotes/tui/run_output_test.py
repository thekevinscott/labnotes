from collections.abc import Iterator
from typing import Any
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.run_output import RunOutput


def stream_log(stream: str, id: str) -> mock.Mock:
    return mock.Mock(stream=stream, id=id, count=0)


def tab(label: str, id: str) -> mock.Mock:
    return mock.Mock(label_text=label, id=id)


@pytest.fixture(autouse=True)
def widgets() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.tui.run_output.StreamLog", side_effect=stream_log) as log,
        mock.patch("labnotes.tui.run_output.Tab", side_effect=tab) as made_tab,
        mock.patch("labnotes.tui.run_output.Tabs") as tabs,
        mock.patch("labnotes.tui.run_output.ContentSwitcher") as switcher,
    ):
        yield {"log": log, "tab": made_tab, "tabs": tabs, "switcher": switcher}


def logs(output: RunOutput) -> dict[str, Any]:
    return output.logs  # type: ignore[return-value]


def tabs(output: RunOutput) -> dict[str, Any]:
    return output.tabs  # type: ignore[return-value]


def labels(output: RunOutput) -> list[str]:
    return [tab.label_text for tab in output.tabs.values()]


def test_starts_on_stdout_with_a_tab_and_log_per_stream() -> None:
    output = RunOutput(id="output")
    assert (output.id, output.current) == ("output", "stdout")
    assert [(log.stream, log.id) for log in output.logs.values()] == [
        ("stdout", "stdout"),
        ("stderr", "stderr"),
    ]
    assert [tab.id for tab in output.tabs.values()] == ["stdout-tab", "stderr-tab"]
    assert labels(output) == ["stdout", "stderr"]
    assert [tab.label for tab in output.tabs.values()] == ["stdout (0)", "stderr (0)"]


def test_shows_the_tabs_above_the_stream_logs(
    widgets: dict[str, mock.MagicMock],
) -> None:
    output = RunOutput()
    assert list(output.compose()) == [
        widgets["tabs"].return_value,
        logs(output)["stdout"],
        logs(output)["stderr"],
    ]
    widgets["tabs"].assert_called_once_with(*output.tabs.values())
    widgets["switcher"].assert_called_once_with(initial="stdout")


def test_follow_reads_each_stream_and_relabels_its_tab(tmp_path: Path) -> None:
    output = RunOutput()
    logs(output)["stdout"].count = 33
    logs(output)["stderr"].count = 5
    output.follow(tmp_path)
    for log in logs(output).values():
        log.follow.assert_called_once_with(tmp_path)
    assert [tab.label for tab in output.tabs.values()] == ["stdout (33)", "stderr (5)"]


def test_leaves_an_unchanged_label_alone() -> None:
    output = RunOutput()
    stdout = tabs(output)["stdout"]
    stdout.label = "kept"
    stdout.label_text = "stdout (0)"
    output.relabel()
    assert stdout.label == "kept"


def test_relabels_a_tab_whose_old_label_sorts_after_the_new_one() -> None:
    output = RunOutput()
    logs(output)["stdout"].count = 33
    tabs(output)["stdout"].label_text = "stdout (5)"
    output.relabel()
    assert tabs(output)["stdout"].label == "stdout (33)"


def test_reset_clears_both_streams_and_their_counts() -> None:
    output = RunOutput()
    logs(output)["stderr"].count = 0
    tabs(output)["stderr"].label_text = "stderr (4)"
    output.reset()
    for log in logs(output).values():
        log.reset.assert_called_once_with()
    assert tabs(output)["stderr"].label == "stderr (0)"


def test_show_switches_the_visible_log_and_the_active_tab(
    widgets: dict[str, mock.MagicMock],
) -> None:
    output = RunOutput()
    switcher, tabs = mock.Mock(), mock.Mock()
    lookup = {widgets["switcher"]: switcher, widgets["tabs"]: tabs}
    with (
        mock.patch.object(
            RunOutput, "is_mounted", new_callable=mock.PropertyMock, return_value=True
        ),
        mock.patch.object(output, "query_one", side_effect=lookup.__getitem__),
    ):
        output.show("stderr")
    assert (output.current, switcher.current, tabs.active) == (
        "stderr",
        "stderr",
        "stderr-tab",
    )


def test_show_before_mounting_only_remembers_the_stream() -> None:
    output = RunOutput()
    with mock.patch.object(output, "query_one") as query:
        output.show("stderr")
    assert output.current == "stderr"
    query.assert_not_called()


@pytest.mark.parametrize(
    ("current", "clicked", "shown"),
    [
        ("stdout", "stderr", ["stderr"]),
        ("stdout", "stdout", []),
        ("stderr", "stdout", ["stdout"]),
        ("".join(["std", "out"]), "stdout", []),
    ],
)
def test_a_clicked_tab_shows_its_stream(
    current: str, clicked: str, shown: list[str]
) -> None:
    output = RunOutput()
    output.current = current
    event = mock.Mock(tab=tabs(output)[clicked])
    with mock.patch.object(output, "show") as show:
        output.on_tabs_tab_activated(event)
    event.stop.assert_called_once_with()
    assert [call.args[0] for call in show.call_args_list] == shown


@pytest.mark.parametrize(
    ("current", "other"), [("stdout", "stderr"), ("stderr", "stdout")]
)
def test_switch_toggles_the_stream_and_focuses_its_log(
    current: str, other: str
) -> None:
    output = RunOutput()
    output.current = current
    output.action_switch()
    assert output.current == other
    logs(output)[other].focus.assert_called_once_with(True)
    logs(output)[current].focus.assert_not_called()


def test_focus_goes_to_the_shown_log() -> None:
    output = RunOutput()
    assert output.focus(scroll_visible=False) is output
    logs(output)["stdout"].focus.assert_called_once_with(False)
