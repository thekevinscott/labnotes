from labnotes.runner.describe_event import describe_event


def describe_status(event: dict[str, object]) -> str:
    match event:
        case {"event": "output"}:
            said = f"{event['run']}: {event['line']}"
        case {"event": "done", "error": None}:
            said = "Done."
        case {"event": "done"}:
            said = f"Stopped: {event['error']}"
        case _:
            said = describe_event(event)
    return f"{event['experiment']}: {said}"
