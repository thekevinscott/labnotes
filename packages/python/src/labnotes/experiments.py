import asyncio
import sys
from pathlib import Path

import click

from labnotes.load_config import load_config
from labnotes.print_rows import print_rows
from labnotes.read_config import CONFIG_FILE
from labnotes.runner.run_headless import run_headless
from labnotes.runner.start_experiment import start_experiment
from labnotes.tables.experiment_rows import experiment_rows
from labnotes.tui.run_tui import run_tui


@click.command(help="List experiments, show one, list its runs, or run it.")
@click.argument("name", required=False)
@click.argument("action", required=False, type=click.Choice(["runs", "run"]))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--concurrency",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="With run: how many runs at once.",
)
@click.option(
    "-e",
    "--experiment-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="With run: read this file instead of the experiment's experiment.toml.",
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="With run: print a line per event instead of the live view.",
)
@click.pass_context
def experiments(
    ctx: click.Context,
    name: str | None,
    action: str | None,
    output_format: str,
    concurrency: int,
    experiment_config: Path | None,
    no_tui: bool,
) -> None:
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(
            f"No {CONFIG_FILE} here. Run labnotes init, or pass -c PATH."
        )
    match name, action:
        case str(), "run":
            live = sys.stdout.isatty() and sys.stderr.isatty() and not no_tui
            drive = run_tui if live else lambda start, title: run_headless(start)
            try:
                results = start_experiment(
                    config, name, experiment_config, concurrency, drive
                )
            except ValueError as error:
                raise click.ClickException(str(error)) from error
            failed = sum(result["exit_code"] != 0 for result in results)
            click.echo(f"{len(results) - failed} passed, {failed} failed.")
            ctx.exit(1 if failed else 0)
    rows = asyncio.run(experiment_rows(config, name, action))
    if rows is None:
        raise click.ClickException(f"No experiment named {name}.")
    print_rows(rows, output_format)
