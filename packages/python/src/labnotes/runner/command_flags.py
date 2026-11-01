import re
from typing import NamedTuple

from labnotes.runner.flag_name import flag_name

OPERATOR = ";&|<>()"
WORD = re.compile(
    rf"""[{OPERATOR}]+|(?:[^\s{OPERATOR}'"\\]|\\.|'[^']*'|"(?:[^"\\]|\\.)*")+""",
    re.DOTALL,
)


class CommandFlag(NamedTuple):
    name: str
    start: int
    end: int
    joined: bool


def command_flags(command: str) -> list[CommandFlag]:
    words = list(WORD.finditer(command))
    flags: list[CommandFlag] = []
    for index, word in enumerate(words):
        name = flag_name(word[0])
        if name is None:
            continue
        joined = "=" in word[0]
        end = word.end()
        if not joined and index + 1 < len(words):
            value = words[index + 1][0]
            if value[0] not in OPERATOR and not value.startswith("-"):
                end = words[index + 1].end()
        flags.append(CommandFlag(name, word.start(), end, joined))
    return flags
