from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.leave_prompt import LeavePrompt


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
        f"{text} Leave them running (enter) / stop them (s) / cancel (esc).",
        id="prompt",
    )


def test_answers_leave_by_default_stop_on_s_and_nothing_on_escape() -> None:
    assert [
        (binding.key, binding.action)  # type: ignore[union-attr]
        for binding in LeavePrompt.BINDINGS
    ] == [
        ("enter,ctrl+c", "dismiss('leave')"),
        ("s", "dismiss('stop')"),
        ("escape", "dismiss"),
    ]
