import json

import click
from rich.console import Console
from rich.table import Table


def print_rows(rows: list[dict[str, object]], output_format: str) -> None:
    match output_format:
        case "json":
            click.echo(json.dumps(rows, indent=2))
            return
    if not rows:
        click.echo("No rows.")
        return
    table = Table(*rows[0].keys())
    for row in rows:
        table.add_row(*("" if value is None else str(value) for value in row.values()))
    Console().print(table)
