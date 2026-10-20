from labnotes.tui.format_elapsed import format_elapsed


def format_duration(seconds: int | None) -> str:
    return "—" if seconds is None else format_elapsed(seconds)
