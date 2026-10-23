from rich.filesize import decimal


def format_bytes(count: int | None) -> str:
    return "" if count is None else decimal(count)
