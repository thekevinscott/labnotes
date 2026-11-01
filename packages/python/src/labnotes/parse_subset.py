def parse_subset(args: list[str]) -> dict[str, list[str]]:
    only: dict[str, list[str]] = {}
    for arg in args:
        param, equals, value = arg.removeprefix("--").partition("=")
        if not arg.startswith("--") or not equals or not param:
            raise ValueError(f"Unexpected {arg}. Pick params with --PARAM=VALUE.")
        only.setdefault(param, []).append(value)
    return only
