import os
from pathlib import Path

import click
from uvicorn.main import main as uvicorn_main

from labnotes.serve_app import DATA_FOLDER, EXPERIMENTS_FOLDER, KERNEL_IDLE_MINUTES

# labnotes owns these; the rest of uvicorn's options pass straight through.
OWN_OPTIONS = {"app", "factory", "app_dir", "version", "host", "port"}


@click.command(help="Serve the experiments and their run data as a local site.")
@click.option(
    "--experiments-folder",
    type=click.Path(path_type=Path),
    envvar=EXPERIMENTS_FOLDER,
    required=True,
    help="One subfolder per experiment, each with a design.yaml and markdown notes.",
)
@click.option(
    "--data-folder",
    type=click.Path(path_type=Path),
    envvar=DATA_FOLDER,
    required=True,
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
    experiments_folder: Path,
    data_folder: Path,
    kernel_idle_minutes: int,
    **server_options: object,
) -> None:
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
