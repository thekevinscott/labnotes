from collections import Counter

from labnotes.runner.command_flags import command_flags
from labnotes.runner.group_args import group_args


def check_args(params: dict[str, list[object]], command: str, args: list[str]) -> None:
    taken = Counter(flag.name for flag in command_flags(command))
    given: set[str] = set()
    for name in (arg.name for arg in group_args(args) if arg.name is not None):
        if name in params:
            raise ValueError(f"--{name} is a param. Pick it with --{name}=VALUE.")
        if taken[name] > 1:
            raise ValueError(
                f"--{name} is in the command more than once, so -- can't override it."
            )
        if taken[name] and name in given:
            raise ValueError(f"--{name} is in -- ARGS more than once.")
        given.add(name)
