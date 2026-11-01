import re
from itertools import zip_longest
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
    for word, after in zip_longest(words, words[1:]):
        name = flag_name(word[0])
        if name is None:
            continue
        joined = "=" in word[0]
        end = word.end()
        if not joined and after is not None:
            value = after[0]
            if value[0] not in OPERATOR and not value.startswith("-"):
                end = after.end()
        flags.append(CommandFlag(name, word.start(), end, joined))
    return flags
