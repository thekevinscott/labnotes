import click
from pytimeparse2 import parse


def parse_timeout(
    _ctx: click.Context, _param: click.Parameter, value: str | None
) -> float | None:
    if value is None:
        return None
    seconds = parse(value)
    if not isinstance(seconds, int | float) or seconds <= 0:
        raise click.BadParameter(
            f"{value!r}: use a duration over 0, like 90, 30s, 10m or 1h30m."
        )
    return seconds
