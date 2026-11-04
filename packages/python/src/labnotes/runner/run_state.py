"""Persist one invocation's run TUI events in the user's state folder."""

import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from labnotes.models import LabnotesConfig
from labnotes.runner.run_folder import run_folder


def journal_folder(runs: Path) -> Path:
    """Keep journals out of the runs folder, where scripts expect only runs."""
    home = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    key = hashlib.sha256(str(runs.resolve()).encode()).hexdigest()[:16]
    return Path(home) / "labnotes" / "run-state" / key


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
            journal_folder(runs) / f"{stamp}-{os.getpid()}-{uuid4().hex[:8]}.jsonl"
        )

    def record(self, event: dict[str, object]) -> None:
        """Write one event before callers display it."""
        at = time.time()
        stored = {**event, "at": at}
        if event["event"] == "retrying":
            stored["retry_at"] = at + float(str(event["seconds"]))
        data = (json.dumps(stored, default=str) + "\n").encode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        with self.path.open("ab") as file:
            file.write(data)

    def read(self) -> list[dict[str, object]]:
        """Return only complete new events."""
        try:
            with self.path.open("rb") as file:
                file.seek(self.offset)
                data = file.read()
        except FileNotFoundError:
            return []
        try:
            end = data.rindex(b"\n") + 1
        except ValueError:
            return []
        self.offset += end
        return [json.loads(line) for line in data[:end].splitlines()]
