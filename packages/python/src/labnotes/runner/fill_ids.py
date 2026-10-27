import shlex
from collections.abc import Mapping


def fill_ids(command: str, ids: Mapping[str, str]) -> str:
    for name, value in ids.items():
        command = command.replace(f"{{{name}}}", shlex.quote(value))
    return command
