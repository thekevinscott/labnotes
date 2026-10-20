import asyncio

import click

from labnotes.daemon.stop_runs import stop_runs
from labnotes.load_config import load_config
from labnotes.read_config import CONFIG_FILE
from labnotes.run_status import run_status
from labnotes.run_control import run_control


@click.group(name="run", help="Control the runs going in this project.")
def run_command() -> None:
    pass


@run_command.command(
    help="Stop every run. Scripts get SIGTERM, then SIGKILL 5 seconds later."
)
@click.pass_context
def stop(ctx: click.Context) -> None:
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(
            f"No {CONFIG_FILE} here. Run labnotes init, or pass -c PATH."
        )
    stopping = asyncio.run(stop_runs(config.root))
    click.echo("Stopping runs." if stopping else "Nothing is running.")


run_command.add_command(run_status)
run_command.add_command(run_control)
