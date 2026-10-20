import asyncio
from collections.abc import Callable

import uvicorn

# Long enough for a TUI restart or a mod reload to reconnect first.
IDLE_EXIT_SECONDS = 15


async def exit_when_idle(server: uvicorn.Server, idle: Callable[[], bool]) -> None:
    quiet = 0
    while quiet < IDLE_EXIT_SECONDS:
        await asyncio.sleep(1)
        quiet = quiet + 1 if idle() else 0
    server.should_exit = True
