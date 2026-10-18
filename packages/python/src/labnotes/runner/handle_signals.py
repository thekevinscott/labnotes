import asyncio
from collections.abc import Callable


def handle_signals(interrupt: Callable[[], None], *signals: int) -> None:
    loop = asyncio.get_running_loop()
    for signal_number in signals:
        loop.add_signal_handler(signal_number, interrupt)
