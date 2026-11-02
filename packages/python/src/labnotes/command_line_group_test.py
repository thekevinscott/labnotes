from unittest import mock

from labnotes.command_line_group import COMMAND_LINE, CommandLineGroup


def test_keeps_the_whole_command_line_for_subcommands() -> None:
    args = ["-c", "a b.toml", "experiments", "exp", "run", "--", "x"]
    with mock.patch(
        "labnotes.command_line_group.click.Group.make_context"
    ) as make_context:
        make_context.return_value = mock.Mock(meta={})

        ctx = CommandLineGroup().make_context("main", args, None, obj=1)

    make_context.assert_called_once_with("main", args, None, obj=1)
    assert ctx is make_context.return_value
    assert ctx.meta == {COMMAND_LINE: "labnotes -c 'a b.toml' experiments exp run -- x"}
