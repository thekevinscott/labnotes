UNITS = ("KB", "MB", "GB", "TB")


def format_bytes(count: int | None) -> str:
    if count is None:
        return ""
    if count < 1000:
        return f"{count} B"
    size = float(count)
    for unit in UNITS:
        size /= 1000
        if size < 1000 or unit == UNITS[-1]:
            break
    return f"{size:.1f} {unit}"
