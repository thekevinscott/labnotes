def format_elapsed(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02}m"
    if minutes:
        return f"{minutes}m {rest:02}s"
    return f"{rest}s"
