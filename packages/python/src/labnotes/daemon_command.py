"""Internal CLI entry point for a detached experiment daemon."""

import asyncio

import click

from labnotes.daemon.server import serve_daemon
from labnotes.load_config import load_config
from labnotes.read_config import CONFIG_FILE


@click.command(hidden=True)
@click.argument("name")
@click.pass_context
def daemon(ctx: click.Context, name: str) -> None:
    """Serve one experiment from a detached process."""
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(f"No {CONFIG_FILE} here.")
    asyncio.run(serve_daemon(config, name))
