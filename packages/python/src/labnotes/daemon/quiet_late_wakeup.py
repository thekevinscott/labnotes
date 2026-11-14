"""Drop asyncio's report of a reader wakeup that lands after its read ended."""

import asyncio
from typing import Any


def quiet_late_wakeup(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    # anyio's socket streams can run a queued reader wakeup after the read
    # was cancelled or closed, which asyncio logs over the TUI on exit.
    if not isinstance(context.get("exception"), asyncio.InvalidStateError):
        loop.default_exception_handler(context)
