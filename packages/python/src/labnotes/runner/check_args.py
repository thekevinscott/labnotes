import shlex


def check_args(params: dict[str, list[object]], command: str, args: list[str]) -> None:
    taken = {flag_name(token) for token in shlex.split(command)} - {None}
    for arg in args:
        name = flag_name(arg)
        if name in params:
            raise ValueError(f"--{name} is a param. Pick it with --{name}=VALUE.")
        if name in taken:
            raise ValueError(f"--{name} is already in the command.")


def flag_name(token: str) -> str | None:
    if not token.startswith("--") or token == "--":
        return None
    return token.removeprefix("--").partition("=")[0] or None
