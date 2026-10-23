def runs_view_command(config: dict[str, object] | None) -> str | None:
    views = (config or {}).get("views")
    command = views.get("runs") if isinstance(views, dict) else None
    return command if isinstance(command, str) and command.strip() else None
