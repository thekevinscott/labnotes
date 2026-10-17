import shlex
from pathlib import Path

from labnotes.runner.param_args import param_args


def shell_command(command: str, folder: Path, params: dict[str, object]) -> str:
    filled = command.replace("{run_dir}", shlex.quote(str(folder)))
    return f"{filled} {shlex.join(param_args(params))}".rstrip()
