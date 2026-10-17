import json


def param_args(params: dict[str, object]) -> list[str]:
    args: list[str] = []
    for name, value in params.items():
        if isinstance(value, bool):
            text = "1" if value else "0"
        elif isinstance(value, str):
            text = value
        elif isinstance(value, list | dict):
            text = json.dumps(value)
        else:
            text = str(value)
        args += [f"--{name.replace('_', '-')}", text]
    return args
