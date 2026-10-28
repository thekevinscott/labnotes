import shlex
from collections.abc import Mapping


def fill_dirs(command: str, dirs: Mapping[str, str], *, quote: bool = True) -> str:
    for name, value in dirs.items():
        command = command.replace(f"{{{name}}}", shlex.quote(value) if quote else value)
    return command
