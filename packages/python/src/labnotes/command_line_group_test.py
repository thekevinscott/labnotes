import click
from click.testing import CliRunner

from labnotes.command_line_group import COMMAND_LINE, CommandLineGroup


def test_keeps_the_whole_command_line_for_subcommands() -> None:
    seen: list[str] = []

    @click.group(cls=CommandLineGroup)
    @click.option("-c")
    def main(c: str | None) -> None:
        pass

    @main.command(context_settings={"ignore_unknown_options": True})
    @click.argument("rest", nargs=-1)
    @click.pass_context
    def sub(ctx: click.Context, rest: tuple[str, ...]) -> None:
        seen.append(ctx.meta[COMMAND_LINE])

    result = CliRunner().invoke(main, ["-c", "a b.toml", "sub", "--m=x", "--", "y"])

    assert result.exit_code == 0, result.output
    assert seen == ["labnotes -c 'a b.toml' sub --m=x -- y"]
