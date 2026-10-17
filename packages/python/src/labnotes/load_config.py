from pathlib import Path

import click

from labnotes.models import LabnotesConfig
from labnotes.read_config import read_config


def load_config(ctx: click.Context) -> LabnotesConfig | None:
    path: Path = ctx.find_root().obj
    try:
        return read_config(path) if path.is_file() else None
    except ValueError as error:
        raise click.ClickException(str(error)) from error
