import asyncio
import typing

import click

from labnotes.daemon.control_run import control_run
from labnotes.load_config import load_config
from labnotes.models import Controls
from labnotes.read_config import CONFIG_FILE

PARAMS = {
    action: typing.get_args(hint)[0]
    for action, hint in typing.get_type_hints(Controls).items()
}


@click.command(
    name="control",
    help=(
        "Send one control to an experiment's runs, as the live view's keys do. "
        "kill takes a run; set_concurrency a number; interrupt and finish nothing."
    ),
)
@click.argument("name")
@click.argument("action", type=click.Choice(list(PARAMS)))
@click.argument("args", nargs=-1)
@click.pass_context
def run_control(
    ctx: click.Context, name: str, action: str, args: tuple[str, ...]
) -> None:
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(
            f"No {CONFIG_FILE} here. Run labnotes init, or pass -c PATH."
        )
    kinds = PARAMS[action]
    if len(args) != len(kinds):
        raise click.UsageError(f"{action} takes {len(kinds)} argument(s).")
    try:
        values = [kind(args[i]) for i, kind in enumerate(kinds)]
    except ValueError:
        raise click.UsageError(f"{action} takes a number.") from None
    refused = asyncio.run(control_run(config.root, name, action, values))
    if refused is not None:
        raise click.ClickException(refused)
