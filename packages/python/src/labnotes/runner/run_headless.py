import asyncio
import signal
from collections.abc import Callable

import click

from labnotes.models import Start
from labnotes.runner.describe_event import describe_event
from labnotes.runner.handle_signals import handle_signals


def run_headless(start: Start) -> list[dict[str, object]]:
    def listen(interrupt: Callable[[], None]) -> None:
        handle_signals(interrupt, signal.SIGINT, signal.SIGTERM, signal.SIGHUP)

    return asyncio.run(start(lambda event: click.echo(describe_event(event)), listen))
