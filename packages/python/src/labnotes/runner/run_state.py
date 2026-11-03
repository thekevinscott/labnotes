"""Persist the run TUI's presentation events under one experiment."""

import json
import os
import time
from tempfile import mkstemp

from labnotes.models import LabnotesConfig


class RunState:
    """Append complete events and replay them from a disk cursor."""

    def __init__(self, config: LabnotesConfig, experiment: str) -> None:
        folder = config.root / config.experiments.replace("{experiment}", experiment)
        self.path = folder / "run-state.jsonl"
        self.offset = 0
        self.inode: int | None = None

    def begin(self) -> None:
        """Start a new invocation without retaining stale presentation state."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = mkstemp(prefix=".run-state-", dir=self.path.parent)
        os.close(fd)
        try:
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def record(self, event: dict[str, object]) -> None:
        """Write one event before callers display it."""
        at = time.time()
        stored = {**event, "at": at}
        if event["event"] == "retrying":
            stored["retry_at"] = at + float(event["seconds"])  # type: ignore[arg-type]
        data = (json.dumps(stored, default=str) + "\n").encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            while data:
                data = data[os.write(fd, data) :]
        finally:
            os.close(fd)

    def read(self) -> list[dict[str, object]]:
        """Return only complete new events, including after a file restart."""
        try:
            with self.path.open("rb") as file:
                stat = os.fstat(file.fileno())
                if self.inode != stat.st_ino or self.offset > stat.st_size:
                    self.offset = 0
                    self.inode = stat.st_ino
                file.seek(self.offset)
                data = file.read()
        except FileNotFoundError:
            return []
        complete = data.rfind(b"\n")
        if complete < 0:
            return []
        self.offset += complete + 1
        return [json.loads(line) for line in data[: complete + 1].splitlines()]
