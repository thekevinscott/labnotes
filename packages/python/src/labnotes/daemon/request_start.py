"""Start or restart an invocation through the daemon, reporting each step."""

import asyncio
import contextlib
import threading
from collections.abc import Callable
from typing import Any

from labnotes.daemon.command import command
from labnotes.daemon.ensure import ensure_daemon
from labnotes.models import LabnotesConfig


async def request_start(
    config: LabnotesConfig,
    name: str,
    request: dict[str, object],
    progress: Callable[[str], None],
) -> dict[str, object]:
    """Return the daemon's accepted reply, waiting as long as it stays alive."""
    progress("Starting up")
    await ensure_daemon(config, name)
    loop = asyncio.get_running_loop()
    reply: asyncio.Future[dict[str, object]] = loop.create_future()

    def post(callback: Callable[..., Any], *args: object) -> None:
        # The loop is gone once the user quits mid-start; drop late news.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(callback, *args)

    def settle(outcome: dict[str, object] | ValueError) -> None:
        if reply.done():
            return
        if isinstance(outcome, ValueError):
            reply.set_exception(outcome)
        else:
            reply.set_result(outcome)

    def send() -> None:
        outcome: dict[str, object] | ValueError
        try:
            outcome = command(config, name, request, lambda step: post(progress, step))
        except ValueError as error:
            outcome = error
        post(settle, outcome)

    # A daemon thread, so quitting never waits on a reply that has no deadline.
    threading.Thread(target=send, daemon=True).start()
    accepted = await reply
    if not accepted.get("ok"):
        raise ValueError(str(accepted.get("error", "Daemon rejected start")))
    return accepted
