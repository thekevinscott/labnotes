from pathlib import Path

import click

from labnotes.context_guide import context_guide
from labnotes.experiments import experiments
from labnotes.init import init
from labnotes.load_config import load_config
from labnotes.read_config import CONFIG_FILE
from labnotes.server import server


@click.group(
    invoke_without_command=True,
    help="Manage experiments in a folder. `labnotes context` prints a guide for"
    " coding agents.",
)
@click.version_option(package_name="labnotes")
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    help=f"Project config. Default: {CONFIG_FILE} in the working folder, if there.",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()
    ctx.obj = config_path or Path.cwd() / CONFIG_FILE


@main.command(help="Print a guide for coding agents.")
@click.pass_context
def context(ctx: click.Context) -> None:
    click.echo(context_guide(load_config(ctx), Path.cwd()), nl=False)


main.add_command(experiments)
main.add_command(init)
main.add_command(server)
