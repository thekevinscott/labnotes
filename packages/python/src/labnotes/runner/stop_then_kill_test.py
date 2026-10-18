import asyncio
from collections.abc import Callable
from unittest import mock

from labnotes.runner.stop_then_kill import stop_then_kill


def test_interrupts_now_and_again_after_the_grace_period() -> None:
    interrupt = mock.Mock()
    handlers: dict[int, Callable[[], None]] = {}
    later: list[tuple[object, ...]] = []

    async def receive() -> None:
        loop = asyncio.get_running_loop()
        with (
            mock.patch.object(
                loop,
                "add_signal_handler",
                side_effect=lambda number, handler: handlers.update({number: handler}),
            ),
            mock.patch.object(
                loop, "call_later", side_effect=lambda *a: later.append(a)
            ),
        ):
            stop_then_kill(interrupt, 15, 1)
            handlers[1]()

    asyncio.run(receive())

    assert sorted(handlers) == [1, 15]
    interrupt.assert_called_once_with()
    assert later == [(5, interrupt)]
