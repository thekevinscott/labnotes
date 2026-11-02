from labnotes.parse_param_value import parse_param_value


def parse_params(pairs: list[str]) -> dict[str, list[object]]:
    params: dict[str, list[object]] = {}
    for pair in pairs:
        name, equals, value = pair.partition("=")
        if not equals or not name:
            raise ValueError(f"--param {pair} must look like NAME=VALUE.")
        params.setdefault(name, []).append(parse_param_value(value))
    return params
