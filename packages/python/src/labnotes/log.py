import json
import os
from datetime import UTC, datetime

from labnotes.log_path import INVOCATION_ENV, log_path


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
    tags: dict[str, object] = {"timestamp": now()}
    if invocation := os.environ.get(INVOCATION_ENV):
        tags = {"invocation": invocation, **tags}
    line = json.dumps({**block, **tags})
    with path.open("a", encoding="utf-8") as file:
        file.write(f"{line}\n")
