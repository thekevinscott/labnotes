import asyncio
from typing import Any

import pytest
from textual.app import App

from labnotes.tui.leave_prompt import LeavePrompt


def answer(count: int, *keys: str) -> tuple[list[str | None], str]:
    answers: list[str | None] = []
    shown: list[str] = []

    async def drive() -> None:
        app: App[None] = App()
        async with app.run_test() as pilot:
            app.push_screen(LeavePrompt(count), answers.append)
            await pilot.pause()
            widget: Any = app.screen.query_one("#prompt")
            shown.append(str(widget.content))
            await pilot.press(*keys)
            await pilot.pause()

    asyncio.run(drive())
    return answers, shown[0]


@pytest.mark.parametrize(
    ("count", "text"),
    [
        (1, "1 run still going."),
        (3, "3 runs still going."),
    ],
)
def test_says_how_many_runs_are_going(count: int, text: str) -> None:
    _, shown = answer(count)
    assert shown == (
        f"{text} Leave them running (enter) / stop them (s) / cancel (esc)."
    )


@pytest.mark.parametrize(
    ("key", "choice"),
    [
        ("enter", "leave"),
        ("ctrl+c", "leave"),
        ("s", "stop"),
        ("escape", None),
    ],
)
def test_answers_with_the_key_pressed(key: str, choice: str | None) -> None:
    answers, _ = answer(2, key)
    assert answers == [choice]
