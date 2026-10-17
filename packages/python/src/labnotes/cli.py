import os
from pathlib import Path

import click
from uvicorn.main import main as uvicorn_main

from labnotes.context_guide import context_guide
from labnotes.models import LabnotesConfig
from labnotes.read_config import CONFIG_FILE, read_config
from labnotes.serve_app import DATA_FOLDER, EXPERIMENTS_FOLDER, KERNEL_IDLE_MINUTES

# labnotes owns these; the rest of uvicorn's options pass straight through.
OWN_OPTIONS = {"app", "factory", "app_dir", "version", "host", "port"}


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


def load_config(ctx: click.Context) -> LabnotesConfig | None:
    path: Path = ctx.obj
    try:
        return read_config(path) if path.is_file() else None
    except ValueError as error:
        raise click.ClickException(str(error)) from error


@main.command(help="Print a guide for coding agents.")
@click.pass_context
def context(ctx: click.Context) -> None:
    click.echo(context_guide(load_config(ctx), Path.cwd()), nl=False)


@main.command(help="Serve the experiments and their run data as a local site.")
@click.option(
    "--experiments-folder",
    type=click.Path(path_type=Path),
    envvar=EXPERIMENTS_FOLDER,
    help="One subfolder per experiment, each with a design.yaml and markdown notes.",
)
@click.option(
    "--data-folder",
    type=click.Path(path_type=Path),
    envvar=DATA_FOLDER,
    help="Run data, with a .dirsql.toml declaring a runs table that has a study column.",
)
@click.option(
    "--kernel-idle-minutes",
    type=click.IntRange(min=1),
    default=30,
    show_default=True,
    envvar=KERNEL_IDLE_MINUTES,
    help="Stop a note's Python kernel after this long without a run.",
)
@click.option(
    "-h",
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Bind to this host. 0.0.0.0 or a Tailscale IP serves beyond localhost.",
)
@click.option("-p", "--port", type=int, default=8000, show_default=True)
@click.pass_context
def server(
    ctx: click.Context,
    experiments_folder: Path | None,
    data_folder: Path | None,
    kernel_idle_minutes: int,
    **server_options: object,
) -> None:
    config = load_config(ctx)
    if config is not None:
        experiments_folder = experiments_folder or config.experiments_folder
        data_folder = data_folder or config.data_folder
    if experiments_folder is None or data_folder is None:
        raise click.UsageError(
            f"--experiments-folder and --data-folder are required without a {CONFIG_FILE}."
        )
    # Through the environment so --reload and --workers child processes see them.
    os.environ[EXPERIMENTS_FOLDER] = str(experiments_folder.resolve())
    os.environ[DATA_FOLDER] = str(data_folder.resolve())
    os.environ[KERNEL_IDLE_MINUTES] = str(kernel_idle_minutes)
    ctx.invoke(
        uvicorn_main,
        app="labnotes.serve_app:serve_app",
        factory=True,
        **server_options,
    )


server.params += [p for p in uvicorn_main.params if p.name not in OWN_OPTIONS]
