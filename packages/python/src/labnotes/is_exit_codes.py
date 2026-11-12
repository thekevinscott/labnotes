def is_exit_codes(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(code, int) and not isinstance(code, bool) and 1 <= code <= 255
        for code in value
    )
