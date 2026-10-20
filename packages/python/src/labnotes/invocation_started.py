import re

STAMP = re.compile(r"(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})")


def invocation_started(name: str) -> str | None:
    found = STAMP.match(name)
    if not found:
        return None
    year, month, day, hour, minute, second = found.groups()
    return f"{year}-{month}-{day} {hour}:{minute}:{second}"
