from itertools import product


def param_grid(params: dict[str, list[object]]) -> list[dict[str, object]]:
    choices = ([(name, value) for value in values] for name, values in params.items())
    return [dict(cell) for cell in product(*choices)]
