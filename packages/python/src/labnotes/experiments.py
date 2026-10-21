import asyncio
import sys
from pathlib import Path

import click

from labnotes.create_experiment import create_experiment
from labnotes.daemon.remote_start import remote_start
from labnotes.load_config import load_config
from labnotes.print_rows import print_rows
from labnotes.read_config import CONFIG_FILE
from labnotes.runner.run_headless import run_headless
from labnotes.tables.experiment_rows import experiment_rows
from labnotes.tui.browse_tui import browse_tui
from labnotes.tui.run_tui import run_tui


@click.command(
    help="List experiments, show one, list its runs, or run it."
    " `new [NAME]` creates one."
)
@click.argument("name", required=False)
@click.argument("action", required=False, metavar="[runs|run]")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    help="Print rows and exit. Unset, a terminal browses them instead;"
    " anything else gets table.",
)
@click.option(
    "--concurrency",
    type=click.IntRange(min=1),
    help="With run: how many runs at once. Overrides experiment.toml and"
    " .labnotes.toml; 1 if none sets it.",
)
@click.option(
    "-e",
    "--experiment-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="With run: read this file instead of the experiment's experiment.toml.",
)
@click.pass_context
def experiments(
    ctx: click.Context,
    name: str | None,
    action: str | None,
    output_format: str | None,
    concurrency: int | None,
    experiment_config: Path | None,
) -> None:
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(
            f"No {CONFIG_FILE} here. Run labnotes init, or pass -c PATH."
        )
    match name, action:
        case "new", _:
            try:
                path = create_experiment(config, action)
            except ValueError as error:
                raise click.ClickException(str(error)) from error
            click.echo(f"Created {path / 'experiment.toml'}")
            return
        case str(), "run":
            start = remote_start(config, name, experiment_config, concurrency)
            try:
                if sys.stdout.isatty() and sys.stderr.isatty():
                    results = run_tui(start, name)
                else:
                    results = run_headless(start)
            except ValueError as error:
                raise click.ClickException(str(error)) from error
            failed = sum(result["exit_code"] != 0 for result in results)
            click.echo(f"{len(results) - failed} passed, {failed} failed.")
            return
    if action not in (None, "runs"):
        raise click.UsageError(f"Unknown action {action}. Use runs or run.")
    if output_format is None and sys.stdout.isatty() and sys.stderr.isatty():
        try:
            browse_tui(config, name)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        return
    try:
        rows = asyncio.run(experiment_rows(config, name, action))
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    if rows is None:
        raise click.ClickException(f"No experiment named {name}.")
    print_rows(rows, output_format or "table")
