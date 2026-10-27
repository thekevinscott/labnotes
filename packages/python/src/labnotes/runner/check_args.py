import shlex

from labnotes.runner.flag_name import flag_name


def check_args(params: dict[str, list[object]], command: str, args: list[str]) -> None:
    taken = {flag_name(token) for token in shlex.split(command)} - {None}
    for arg in args:
        name = flag_name(arg)
        if name in params:
            raise ValueError(f"--{name} is a param. Pick it with --{name}=VALUE.")
        if name in taken:
            raise ValueError(f"--{name} is already in the command.")
