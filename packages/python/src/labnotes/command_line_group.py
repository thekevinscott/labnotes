import shlex
from typing import Any

import click

COMMAND_LINE = "labnotes.command_line"


class CommandLineGroup(click.Group):
    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: Any,
    ) -> click.Context:
        command_line = shlex.join(["labnotes", *args])
        ctx = super().make_context(info_name, args, parent, **extra)
        ctx.meta[COMMAND_LINE] = command_line
        return ctx
