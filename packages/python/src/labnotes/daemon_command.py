import click

from labnotes.daemon.serve_daemon import serve_daemon
from labnotes.load_config import load_config
from labnotes.read_config import CONFIG_FILE


@click.command(name="daemon", hidden=True)
@click.pass_context
def daemon_command(ctx: click.Context) -> None:
    config = load_config(ctx)
    if config is None:
        raise click.ClickException(f"No {CONFIG_FILE} here.")
    serve_daemon(config)
