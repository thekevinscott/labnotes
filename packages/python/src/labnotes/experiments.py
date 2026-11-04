import asyncio
import sys
from pathlib import Path

import click

from labnotes.command_line_group import COMMAND_LINE
from labnotes.create_experiment import create_experiment
from labnotes.daemon.command import command as daemon_command
from labnotes.daemon.ensure import ensure_daemon
from labnotes.runner.start_experiment import start_experiment
from labnotes.runner.run_state import RunState
from labnotes.utils.format_bytes import format_bytes
from labnotes.load_config import load_config
from labnotes.parse_params import parse_params
from labnotes.parse_subset import parse_subset
from labnotes.print_rows import print_rows
from labnotes.read_config import CONFIG_FILE
from labnotes.runner.run_headless import run_headless
from labnotes.tables.experiment_rows import experiment_rows
from labnotes.tui.browse_tui import browse_tui
from labnotes.tui.run_tui import run_tui

BYTES = ("memory", "size")
PASSTHROUGH = "labnotes.passthrough"


class PassthroughCommand(click.Command):
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if "--" in args:
            at = args.index("--")
            ctx.meta[PASSTHROUGH] = args[at + 1 :]
            args = args[:at]
        return super().parse_args(ctx, args)


@click.command(
    cls=PassthroughCommand,
    help="List experiments, show one, list its runs, or run it."
    " `new [NAME]` creates one, from --command, --param, --repeats and"
    " --from OTHER if given. With run, --PARAM=VALUE runs only the"
    " matrix cells where that param has that value (repeat it for several"
    " values), and anything after --"
    " is appended to every run's command and recorded in run.json, so never"
    " pass secrets there.",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("name", required=False)
@click.argument("action", required=False, metavar="[runs|run|stop]")
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
@click.option("--run-id", help="With run: restart only this failed run by id.")
@click.option(
    "--headless",
    is_flag=True,
    help="With run: keep the scheduler in this foreground process.",
)
@click.option(
    "-e",
    "--experiment-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="With run: read this file instead of the experiment's experiment.toml.",
)
@click.option(
    "--timeout",
    type=click.IntRange(min=1),
    metavar="SECONDS",
    help="With run: stop any run still going after this many seconds."
    " Unset, runs have no time limit.",
)
@click.option(
    "--setup",
    metavar="COMMAND",
    help="With run: shell command to run once before any run starts."
    " Overrides experiment.toml and .labnotes.toml.",
)
@click.option(
    "--teardown",
    metavar="COMMAND",
    help="With run: shell command to run once after every run ends."
    " Overrides experiment.toml and .labnotes.toml.",
)
@click.option(
    "--command",
    metavar="COMMAND",
    help="With new: the experiment's command.",
)
@click.option(
    "--param",
    "params",
    multiple=True,
    metavar="NAME=VALUE",
    help="With new: a value for a param, parsed as TOML or else taken as a"
    " string. Repeat it for several values.",
)
@click.option(
    "--repeats",
    type=click.IntRange(min=1),
    help="With new: how many times each combination runs.",
)
@click.option(
    "--from",
    "source",
    metavar="OTHER",
    help="With new: start from OTHER's experiment.toml and files, never its"
    " runs. Other flags replace the copied values.",
)
@click.pass_context
def experiments(
    ctx: click.Context,
    name: str | None,
    action: str | None,
    output_format: str | None,
    concurrency: int | None,
    run_id: str | None,
    headless: bool,
    experiment_config: Path | None,
    timeout: int | None,
    setup: str | None,
    teardown: str | None,
    command: str | None,
    params: tuple[str, ...],
    repeats: int | None,
    source: str | None,
) -> None:
    passthrough: list[str] | None = ctx.meta.get(PASSTHROUGH)
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(
            f"No {CONFIG_FILE} here. Run labnotes init, or pass -c PATH."
        )
    if name != "new":
        given = {
            "--command": command,
            "--param": params or None,
            "--repeats": repeats,
            "--from": source,
        }
        for flag, value in given.items():
            if value is not None:
                raise click.UsageError(f"{flag} needs new.")
    if headless and action != "run":
        raise click.UsageError("--headless needs run.")
    match name, action:
        case "new", _:
            try:
                path = create_experiment(
                    config, action, source, command, repeats, parse_params(list(params))
                )
            except ValueError as error:
                raise click.ClickException(str(error)) from error
            click.echo(f"Created {path / 'experiment.toml'}")
            return
        case str(), "run":
            if run_id is not None and (ctx.args or passthrough is not None):
                raise click.UsageError(
                    "--run-id uses the run's recorded params and -- ARGS."
                )
            try:
                only = parse_subset(ctx.args)
            except ValueError as error:
                raise click.UsageError(str(error)) from error
            try:
                if not headless and sys.stdout.isatty() and sys.stderr.isatty():
                    asyncio.run(ensure_daemon(config, name))
                    reply = daemon_command(
                        config,
                        name,
                        {
                            "command": "restart" if run_id else "start",
                            "options": {
                                "experiment_config": str(experiment_config)
                                if experiment_config
                                else None,
                                "concurrency": concurrency,
                                "timeout": timeout,
                                "only": only,
                                "args": passthrough or None,
                                "setup": setup,
                                "teardown": teardown,
                                "command_line": ctx.meta.get(COMMAND_LINE),
                                "run_id": run_id,
                            },
                        },
                    )
                    if not reply.get("ok"):
                        raise ValueError(
                            str(reply.get("error", "Daemon rejected start"))
                        )
                    run_tui(
                        None,
                        name,
                        config,
                        experiment_config,
                        daemon_journal=RunState(Path(str(reply["journal"]))),
                    )
                    return
                else:
                    results = run_headless(
                        start_experiment(
                            config,
                            name,
                            experiment_config,
                            concurrency,
                            timeout,
                            only,
                            passthrough or None,
                            setup,
                            teardown,
                            ctx.meta.get(COMMAND_LINE),
                            run_id,
                        )
                    )
            except ValueError as error:
                raise click.ClickException(str(error)) from error
            superseded = {r["retry_of"] for r in results if "retry_of" in r}
            retried = sum(result.get("run") in superseded for result in results)
            failed = sum(
                result["exit_code"] != 0 and result.get("run") not in superseded
                for result in results
            )
            again = f" {retried} retried." if retried else ""
            passed = len(results) - failed - retried
            click.echo(f"{passed} passed, {failed} failed.{again}")
            return
        case str(), "stop":
            if (
                output_format is not None
                or concurrency is not None
                or run_id is not None
                or experiment_config is not None
                or timeout is not None
                or setup is not None
                or teardown is not None
                or passthrough is not None
                or ctx.args
            ):
                raise click.UsageError("stop takes no run or listing options.")
            try:
                reply = daemon_command(config, name, {"command": "stop_all"})
            except ValueError as error:
                raise click.ClickException(str(error)) from error
            if not reply.get("ok"):
                raise click.ClickException(
                    str(reply.get("error", "Daemon rejected stop"))
                )
            click.echo(f"Asked daemon for {name} to stop all runs.")
            return
    if passthrough is not None:
        raise click.UsageError("-- ARGS needs run.")
    if run_id is not None:
        raise click.UsageError("--run-id needs run.")
    if ctx.args:
        raise click.UsageError(f"Unexpected {ctx.args[0]}. --PARAM=VALUE needs run.")
    if action not in (None, "runs"):
        raise click.UsageError(f"Unknown action {action}. Use runs, run or stop.")
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
    if output_format != "json":
        rows = [
            row | {key: format_bytes(row[key]) for key in BYTES if key in row}  # type: ignore[arg-type]
            for row in rows
        ]
    print_rows(rows, output_format or "table")
