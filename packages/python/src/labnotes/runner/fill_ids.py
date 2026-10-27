import shlex
from collections.abc import Mapping


def fill_ids(command: str, ids: Mapping[str, str], *, quote: bool = True) -> str:
    for name, value in ids.items():
        command = command.replace(f"{{{name}}}", shlex.quote(value) if quote else value)
    return command
