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
        mock.patch(
            "labnotes.runner.run_headless.signal",
            mock.Mock(SIGINT=2, SIGTERM=15, SIGHUP=1),
        ),
        mock.patch("labnotes.runner.run_headless.stop_then_kill") as stop_then_kill,
    ):
        yield {"click": click, "stop_then_kill": stop_then_kill}


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


def test_interrupts_on_ctrl_c_terminate_and_hang_up(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    interrupt = mock.Mock()

    async def start(
        report: object, listen: Callable[[Callable[[], None]], None]
    ) -> list[dict[str, object]]:
        listen(interrupt)
        return []

    with mock.patch("labnotes.runner.run_headless.asyncio") as fake_asyncio:
        fake_asyncio.run.side_effect = asyncio.run
        run_headless(start)  # type: ignore[arg-type]

    loop = fake_asyncio.get_running_loop.return_value
    loop.add_signal_handler.assert_called_once_with(2, interrupt)
    collaborators["stop_then_kill"].assert_called_once_with(interrupt, 15, 1)
