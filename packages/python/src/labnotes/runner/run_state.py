"""Persist one invocation's run TUI events under its experiment's runs folder."""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

from labnotes.models import LabnotesConfig
from labnotes.runner.run_folder import run_folder


class RunState:
    """Append complete events and replay them from a disk cursor."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0

    @classmethod
    def create(cls, config: LabnotesConfig, experiment: str) -> "RunState":
        """Choose a journal unique to this invocation without touching disk yet."""
        runs = run_folder(config.root, config.runs, experiment, "_").parent
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        return cls(
            runs / "run-state" / f"{stamp}-{os.getpid()}-{uuid4().hex[:8]}.jsonl"
        )

    def record(self, event: dict[str, object]) -> None:
        """Write one event before callers display it."""
        at = time.time()
        stored = {**event, "at": at}
        if event["event"] == "retrying":
            stored["retry_at"] = at + float(str(event["seconds"]))
        data = (json.dumps(stored, default=str) + "\n").encode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            while data:
                data = data[os.write(fd, data) :]
        finally:
            os.close(fd)

    def read(self) -> list[dict[str, object]]:
        """Return only complete new events."""
        try:
            with self.path.open("rb") as file:
                file.seek(self.offset)
                data = file.read()
        except FileNotFoundError:
            return []
        complete = data.rfind(b"\n")
        if complete < 0:
            return []
        self.offset += complete + 1
        return [json.loads(line) for line in data[: complete + 1].splitlines()]
