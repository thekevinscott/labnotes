import shlex

from labnotes.runner.command_flags import command_flags
from labnotes.runner.group_args import group_args


def override_flags(command: str, args: list[str]) -> tuple[str, list[str]]:
    flags = {flag.name: flag for flag in command_flags(command)}
    replaced: list[tuple[int, int, str]] = []
    rest: list[str] = []
    for arg in group_args(args):
        flag = flags.get(arg.name) if arg.name is not None else None
        if flag is None:
            rest += arg.tokens
        elif arg.value is not None:
            separator = "=" if flag.joined else " "
            text = f"--{arg.name}{separator}{shlex.quote(arg.value)}"
            replaced.append((flag.start, flag.end, text))
    for start, end, text in sorted(replaced, reverse=True):
        command = command[:start] + text + command[end:]
    return command, rest
