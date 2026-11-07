from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.leave_prompt import DetachedLeavePrompt, LeavePrompt


@pytest.fixture(autouse=True)
def static() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.tui.leave_prompt.Static", return_value="prompt"
    ) as patched:
        yield patched


@pytest.mark.parametrize(
    ("count", "text"),
    [
        (0, "0 runs still going."),
        (1, "1 run still going."),
        (3, "3 runs still going."),
    ],
)
def test_says_how_many_runs_are_going(
    static: mock.MagicMock, count: int, text: str
) -> None:
    assert list(LeavePrompt(count).compose()) == ["prompt"]
    static.assert_called_once_with(
        f"{text} Stop them (enter or s) / cancel (esc).",
        id="prompt",
    )


def test_answers_leave_by_default_stop_on_s_and_nothing_on_escape() -> None:
    assert [
        (binding.key, binding.action)  # type: ignore[union-attr]
        for binding in LeavePrompt.BINDINGS
    ] == [
        ("enter,ctrl+c,s", "dismiss('stop')"),
        ("escape", "dismiss"),
    ]


def test_detached_prompt_offers_stop_leave_and_cancel(static: mock.MagicMock) -> None:
    prompt = DetachedLeavePrompt("Setting up.")
    assert list(prompt.compose()) == ["prompt"]
    assert isinstance(prompt, LeavePrompt)
    static.assert_called_once_with(
        "Setting up. Stop (s) / leave running (enter or l) / cancel (esc).",
        id="prompt",
    )
    assert [
        (binding.key, binding.action)  # type: ignore[union-attr]
        for binding in DetachedLeavePrompt.BINDINGS
    ] == [
        ("s", "dismiss('stop')"),
        ("enter,l", "dismiss('leave')"),
        ("escape", "dismiss"),
    ]
