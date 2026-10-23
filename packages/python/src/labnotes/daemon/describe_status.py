from labnotes.format_bytes import format_bytes
from labnotes.runner.describe_event import describe_event


def describe_status(event: dict[str, object]) -> str:
    match event:
        case {"event": "output"}:
            said = f"{event['run']}: {event['line']}"
        case {"event": "usage"}:
            memory = format_bytes(event["memory"]) or "?"  # type: ignore[arg-type]
            size = format_bytes(event["size"]) or "?"  # type: ignore[arg-type]
            said = f"{event['run']} uses {memory} of memory, {size} on disk."
        case {"event": "done", "error": None}:
            said = "Done."
        case {"event": "done"}:
            said = f"Stopped: {event['error']}"
        case _:
            said = describe_event(event)
    return f"{event['experiment']}: {said}"
