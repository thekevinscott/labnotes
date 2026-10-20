import asyncio
import contextlib
import json

import click

from labnotes.daemon.describe_status import describe_status
from labnotes.daemon.watch_status import watch_status
from labnotes.load_config import load_config
from labnotes.read_config import CONFIG_FILE


@click.command(name="status", help="Show what the runs in this project are doing.")
@click.option("--follow", "-f", is_flag=True, help="Keep reporting until interrupted.")
@click.option("--json", "as_json", is_flag=True, help="One JSON event per line.")
@click.pass_context
def run_status(ctx: click.Context, follow: bool, as_json: bool) -> None:
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(
            f"No {CONFIG_FILE} here. Run labnotes init, or pass -c PATH."
        )

    def emit(event: dict[str, object]) -> None:
        line = json.dumps(event, default=str) if as_json else describe_status(event)
        click.echo(line)

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(watch_status(config.root, follow, emit))
