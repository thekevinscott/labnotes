"""Frame one server-sent event."""

import json


def sse(data: object, event: str | None = None, id: str | None = None) -> str:
    """Encode data as one JSON event, named when the stream mixes kinds."""
    name = f"event: {event}\n" if event is not None else ""
    marker = f"id: {id}\n" if id is not None else ""
    return f"{name}{marker}data: {json.dumps(data)}\n\n"
