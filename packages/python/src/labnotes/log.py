import json
from datetime import UTC, datetime

from labnotes.log_path import log_path


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def log(block: dict[str, object]) -> None:
    """Write a block to the run's log, or print its content outside a run.

    Scripts import this, so the module stays standard-library only.
    """
    path = log_path()
    if path is None:
        if "content" in block:
            print(block["content"])
        return
    line = json.dumps({**block, "timestamp": now()})
    with path.open("a", encoding="utf-8") as file:
        file.write(f"{line}\n")
