from labnotes.runner.placeholders import PLACEHOLDERS


def check_hook_placeholders(hooks: dict[str, str | None]) -> None:
    for hook, command in hooks.items():
        for name in PLACEHOLDERS:
            if command is not None and f"{{{name}}}" in command:
                raise ValueError(
                    f"{hook} command {command} uses {{{name}}}; setup, teardown, "
                    "and meta get no folder placeholders. "
                    "Share values with set_state() and get_state()."
                )
