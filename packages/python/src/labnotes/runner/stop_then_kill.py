import asyncio
from collections.abc import Callable

GRACE_SECONDS = 5


def stop_then_kill(interrupt: Callable[[], None], *signals: int) -> None:
    loop = asyncio.get_running_loop()

    def stop() -> None:
        interrupt()
        loop.call_later(GRACE_SECONDS, interrupt)

    for signal_number in signals:
        loop.add_signal_handler(signal_number, stop)
