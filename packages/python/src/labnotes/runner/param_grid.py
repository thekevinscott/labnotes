from itertools import product


def param_grid(params: dict[str, list[object]]) -> list[dict[str, object]]:
    return [
        dict(zip(params, values, strict=True)) for values in product(*params.values())
    ]
