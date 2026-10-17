import asyncio

import click

from labnotes.load_config import load_config
from labnotes.print_rows import print_rows
from labnotes.read_config import CONFIG_FILE
from labnotes.tables.experiment_rows import experiment_rows


@click.command(help="List experiments, show one, or list its runs.")
@click.argument("name", required=False)
@click.argument("action", required=False, type=click.Choice(["runs"]))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.pass_context
def experiments(
    ctx: click.Context, name: str | None, action: str | None, output_format: str
) -> None:
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(
            f"No {CONFIG_FILE} here. Run labnotes init, or pass -c PATH."
        )
    rows = asyncio.run(experiment_rows(config, name, action))
    if rows is None:
        raise click.ClickException(f"No experiment named {name}.")
    print_rows(rows, output_format)
