def parse_subset(args: list[str]) -> dict[str, str]:
    only: dict[str, str] = {}
    for arg in args:
        param, equals, value = arg.removeprefix("--").partition("=")
        if not arg.startswith("--") or not equals or not param:
            raise ValueError(f"Unexpected {arg}. Pick params with --PARAM=VALUE.")
        if param in only:
            raise ValueError(f"--{param} given twice. Pass one value per param.")
        only[param] = value
    return only
