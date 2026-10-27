def flag_name(token: str) -> str | None:
    if not token.startswith("--"):
        return None
    return token.removeprefix("--").partition("=")[0] or None
