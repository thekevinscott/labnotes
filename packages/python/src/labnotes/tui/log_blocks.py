import json
from pathlib import Path

from textual.containers import VerticalScroll

from labnotes.tui.log_block import LogBlock

STREAMING = ("start", "delta")


class LogBlocks(VerticalScroll):
    DEFAULT_CSS = "LogBlocks { height: auto; max-height: 50%; }"

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self.reset()

    def reset(self) -> None:
        self.read_to = 0
        self.streaming: dict[object, LogBlock] = {}
        self.remove_children()
        self.display = False

    def follow(self, folder: Path) -> None:
        path = folder / "log.jsonl"
        if not path.exists():
            return
        with path.open("rb") as log:
            log.seek(self.read_to)
            data = log.read()
        complete = data[: data.rfind(b"\n") + 1]
        self.read_to += len(complete)
        for line in complete.splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                self.add(record)

    def add(self, record: dict[str, object]) -> None:
        phase, key = record.get("phase"), record.get("id")
        body = str(record.get("content", ""))
        if phase == "delta" and key in self.streaming:
            self.streaming[key].extend(body)
            return
        if phase == "stop":
            if key in self.streaming:
                self.streaming.pop(key).extend(body)
            return
        block = LogBlock(body)
        if phase in STREAMING:
            self.streaming[key] = block
        self.mount(block)
        self.display = True
