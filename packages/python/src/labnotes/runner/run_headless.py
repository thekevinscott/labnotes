import asyncio
import signal

import click

from labnotes.models import Controls, Start
from labnotes.runner.describe_event import describe_event
from labnotes.runner.stop_then_kill import stop_then_kill


def run_headless(start: Start) -> list[dict[str, object]]:
    def listen(controls: Controls) -> None:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, controls.interrupt)
        stop_then_kill(controls.interrupt, signal.SIGTERM, signal.SIGHUP)

    return asyncio.run(start(lambda event: click.echo(describe_event(event)), listen))
