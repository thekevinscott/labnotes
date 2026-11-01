import shlex
from collections.abc import Sequence
from pathlib import Path

from labnotes.runner.override_flags import override_flags
from labnotes.runner.param_args import param_args


def shell_command(
    command: str, folder: Path, params: dict[str, object], args: Sequence[str] = ()
) -> str:
    filled = command.replace("{run_dir}", shlex.quote(str(folder)))
    overridden, rest = override_flags(filled, list(args))
    return f"{overridden} {shlex.join([*param_args(params), *rest])}".rstrip()
