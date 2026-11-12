"""Stamp a run event with its time before anyone displays it."""

import json
import time


def stamp_event(event: dict[str, object]) -> dict[str, object]:
    at = time.time()
    stamped = {**event, "at": at}
    if event["event"] == "retrying":
        stamped["retry_at"] = at + float(str(event["seconds"]))
    return json.loads(json.dumps(stamped, default=str))
