import asyncio
from unittest import mock

from labnotes.runner.handle_signals import handle_signals


def test_interrupts_on_each_signal() -> None:
    interrupt = mock.Mock()
    handlers: list[tuple[object, ...]] = []

    async def listen() -> None:
        loop = asyncio.get_running_loop()
        with mock.patch.object(
            loop, "add_signal_handler", side_effect=lambda *a: handlers.append(a)
        ):
            handle_signals(interrupt, 2, 15)

    asyncio.run(listen())

    assert handlers == [(2, interrupt), (15, interrupt)]
