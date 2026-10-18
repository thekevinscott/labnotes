import asyncio
import signal
from collections.abc import Callable

import click

from labnotes.models import Start
from labnotes.runner.describe_event import describe_event


def run_headless(start: Start) -> list[dict[str, object]]:
    def listen(interrupt: Callable[[], None]) -> None:
        asyncio.get_running_loop().add_signal_handler(signal.SIGINT, interrupt)

    return asyncio.run(start(lambda event: click.echo(describe_event(event)), listen))
