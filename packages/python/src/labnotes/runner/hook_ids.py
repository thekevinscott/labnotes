def hook_ids(
    hooks: dict[str, str | None], invocation: str, runs: list[str]
) -> dict[str, str]:
    match runs:
        case [run]:
            return {"run_id": run, "invocation_id": invocation}
    for hook, command in hooks.items():
        if command is not None and "{run_id}" in command:
            raise ValueError(
                f"{hook} command {command} uses {{run_id}}, but this invocation plans "
                f"{len(runs)} runs. {{run_id}} needs exactly one; "
                "use {invocation_id} instead."
            )
    return {"invocation_id": invocation}
