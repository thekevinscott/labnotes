from pathlib import Path

import click

from labnotes.default_config_text import default_config_text
from labnotes.read_config import CONFIG_FILE


@click.command(help=f"Write a {CONFIG_FILE} with the default layout here.")
def init() -> None:
    path = Path.cwd() / CONFIG_FILE
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(default_config_text())
    except FileExistsError as error:
        raise click.ClickException(f"{path} already exists.") from error
    click.echo(f"Wrote {path}")
