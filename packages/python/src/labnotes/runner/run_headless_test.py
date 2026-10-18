import asyncio
from collections.abc import Callable, Iterator
from unittest import mock

import pytest

from labnotes.runner.run_headless import run_headless


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.runner.run_headless.describe_event",
            side_effect=lambda event: f"line {event['n']}",
        ),
        mock.patch("labnotes.runner.run_headless.click") as click,
        mock.patch("labnotes.runner.run_headless.signal", mock.Mock(SIGINT=2)),
    ):
        yield {"click": click}


def test_prints_each_event_and_returns_the_results(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def start(
        report: Callable[[dict[str, object]], None], listen: object
    ) -> list[dict[str, object]]:
        report({"n": 1})
        return [{"exit_code": 0}]

    assert run_headless(start) == [{"exit_code": 0}]  # type: ignore[arg-type]
    collaborators["click"].echo.assert_called_once_with("line 1")


def test_interrupts_on_sigint(collaborators: dict[str, mock.MagicMock]) -> None:
    interrupt = mock.Mock()
    handlers: list[tuple[object, ...]] = []

    async def start(
        report: object, listen: Callable[[Callable[[], None]], None]
    ) -> list[dict[str, object]]:
        loop = asyncio.get_running_loop()
        with mock.patch.object(
            loop, "add_signal_handler", side_effect=lambda *a: handlers.append(a)
        ):
            listen(interrupt)
        return []

    run_headless(start)  # type: ignore[arg-type]

    assert handlers == [(2, interrupt)]
