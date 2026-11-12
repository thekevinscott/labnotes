import codecs
import os
from pathlib import Path
from typing import BinaryIO

from textual.widgets import Log

from labnotes.utils.format_bytes import format_bytes

TAIL_BYTES = 64 * 1024
SNIFF_BYTES = 8 * 1024
MAX_LINES = 10_000


class FileTail(Log):
    """Show the end of one file, then what gets appended to it."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__(max_lines=MAX_LINES, id=id)
        self.path: Path | None = None
        self.restart()

    def restart(self) -> None:
        self.read_to = 0
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def open(self, path: Path) -> None:
        self.path = path
        self.restart()
        self.follow()

    def follow(self) -> None:
        if self.path is None:
            return
        try:
            with self.path.open("rb") as file:
                self.read(file, os.fstat(file.fileno()).st_size)
        except OSError:
            self.restart()
            self.clear().write(f"{self.path.name} is gone.")

    def read(self, file: BinaryIO, size: int) -> None:
        if size < self.read_to:
            self.restart()
        if self.read_to == 0:
            self.clear()
            if b"\0" in file.read(SNIFF_BYTES):
                self.write(
                    f"{Path(file.name).name} is binary ({format_bytes(size)}), "
                    "so it isn't shown."
                )
                return
        start = max(self.read_to, size - TAIL_BYTES)
        if start > self.read_to:
            self.write(f"[skipped {format_bytes(start - self.read_to)}]\n")
        file.seek(start)
        data = file.read(size - start)
        self.read_to = start + len(data)
        self.write(self.decoder.decode(data))
