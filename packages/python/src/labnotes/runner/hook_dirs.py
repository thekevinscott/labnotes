def hook_dirs(
    hooks: dict[str, str | None], invocation_dir: str | None, run_dirs: list[str]
) -> dict[str, str]:
    match run_dirs:
        case [run_dir]:
            invocation_dir = invocation_dir or run_dir
    available = {"invocation_dir": invocation_dir} if invocation_dir is not None else {}
    for hook, command in hooks.items():
        if command is None:
            continue
        if "{run_dir}" in command:
            raise ValueError(
                f"{hook} command {command} uses {{run_dir}}; "
                "use {invocation_dir} instead."
            )
        if "{invocation_dir}" in command and invocation_dir is None:
            raise ValueError(
                f"{hook} command {command} uses {{invocation_dir}}, but this "
                f"invocation plans {len(run_dirs)} runs and has no shared folder."
            )
    return available
