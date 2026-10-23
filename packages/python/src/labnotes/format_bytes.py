UNITS = ("KB", "MB", "GB", "TB")


def format_bytes(count: int | None) -> str:
    if count is None:
        return ""
    if count < 1000:
        return f"{count} B"
    size = count / 1000
    for unit in UNITS[:-1]:
        if size < 1000:
            return f"{size:.1f} {unit}"
        size /= 1000
    return f"{size:.1f} {UNITS[-1]}"
