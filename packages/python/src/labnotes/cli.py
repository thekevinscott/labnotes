import asyncio
import json
import os
from pathlib import Path

import click
from uvicorn.main import main as uvicorn_main

from labnotes.dump_experiments import dump_experiments
from labnotes.serve_app import DATA_FOLDER, EXPERIMENTS_FOLDER

# labnotes owns these; the rest of uvicorn's options pass straight through.
OWN_OPTIONS = {"app", "factory", "app_dir", "version", "host", "port"}


@click.command(help="Browse experiments and their run data.")
@click.version_option(package_name="labnotes")
@click.option(
    "--experiments-folder",
    type=click.Path(path_type=Path),
    required=True,
    envvar=EXPERIMENTS_FOLDER,
    help="One subfolder per experiment, each with a design.yaml and markdown notes.",
)
@click.option(
    "--data-folder",
    type=click.Path(path_type=Path),
    required=True,
    envvar=DATA_FOLDER,
    help="Run data, with a .dirsql.toml declaring a runs table that has a study column.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print experiments as JSON instead of serving.",
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
def main(
    ctx: click.Context,
    experiments_folder: Path,
    data_folder: Path,
    as_json: bool,
    **server_options: object,
) -> None:
    if as_json:
        experiments = asyncio.run(dump_experiments(experiments_folder, data_folder))
        click.echo(json.dumps(experiments, indent=2))
        return
    # Through the environment so --reload and --workers child processes see them.
    os.environ[EXPERIMENTS_FOLDER] = str(experiments_folder.resolve())
    os.environ[DATA_FOLDER] = str(data_folder.resolve())
    ctx.invoke(
        uvicorn_main,
        app="labnotes.serve_app:serve_app",
        factory=True,
        **server_options,
    )


main.params += [p for p in uvicorn_main.params if p.name not in OWN_OPTIONS]
