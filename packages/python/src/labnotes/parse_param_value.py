import tomllib


def parse_param_value(value: str) -> object:
    try:
        return tomllib.loads(f"value = {value}")["value"]
    except tomllib.TOMLDecodeError:
        return value
