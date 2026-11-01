from typing import NamedTuple

from labnotes.runner.flag_name import flag_name


class Arg(NamedTuple):
    name: str | None
    value: str | None
    tokens: list[str]


def group_args(args: list[str]) -> list[Arg]:
    grouped: list[Arg] = []
    values = {
        index + 1
        for index, token in enumerate(args[:-1])
        if flag_name(token) is not None
        and "=" not in token
        and not args[index + 1].startswith("-")
    }
    for index, token in enumerate(args):
        name = flag_name(token)
        if index in values:
            continue
        if name is None:
            grouped.append(Arg(None, None, [token]))
        elif "=" in token:
            grouped.append(Arg(name, token.partition("=")[2], [token]))
        elif index + 1 in values:
            grouped.append(Arg(name, args[index + 1], [token, args[index + 1]]))
        else:
            grouped.append(Arg(name, None, [token]))
    return grouped
