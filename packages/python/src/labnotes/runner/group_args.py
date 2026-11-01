from typing import NamedTuple

from labnotes.runner.flag_name import flag_name


class Arg(NamedTuple):
    name: str | None
    value: str | None
    tokens: list[str]


def group_args(args: list[str]) -> list[Arg]:
    grouped: list[Arg] = []
    index = 0
    while index < len(args):
        token = args[index]
        index += 1
        name = flag_name(token)
        if name is None:
            grouped.append(Arg(None, None, [token]))
        elif "=" in token:
            grouped.append(Arg(name, token.partition("=")[2], [token]))
        elif index < len(args) and not args[index].startswith("-"):
            grouped.append(Arg(name, args[index], [token, args[index]]))
            index += 1
        else:
            grouped.append(Arg(name, None, [token]))
    return grouped
