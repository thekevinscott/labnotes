from bisect import bisect_left
from pathlib import Path
from typing import BinaryIO

BLOCK = 65_536
MAX_LINE = 65_536


class LineIndex:
    # breaks[i] counts the newlines before byte i * BLOCK, so finding a line
    # reads one block and the index stays a few KB for a GB log.

    def __init__(self, path: Path) -> None:
        self.path = path
        self.breaks = [0]
        self.scanned = 0
        self.lines = 0
        self.partial = False

    @property
    def rows(self) -> int:
        return self.lines + self.partial

    def extend(self) -> bool:
        grew = False
        with self.path.open("rb") as file:
            file.seek(self.scanned)
            while data := file.read(BLOCK - self.scanned % BLOCK):
                grew = True
                self.lines += data.count(b"\n")
                self.partial = not data.endswith(b"\n")
                self.scanned += len(data)
                if not self.scanned % BLOCK:
                    self.breaks.append(self.lines)
        return grew

    def start(self, line: int, file: BinaryIO) -> int:
        if line == 0:
            return 0
        block = bisect_left(self.breaks, line) - 1
        offset = block * BLOCK
        file.seek(offset)
        data = file.read(min(BLOCK, self.scanned - offset))  # probe
        at = -1
        for _ in range(line - self.breaks[block]):
            at = data.index(b"\n", at + 1)
        return offset + at + 1

    def seek(self, line: int, file: BinaryIO) -> int:
        position = self.start(line, file)
        file.seek(position)
        return self.scanned - position

    def read(self, first: int, count: int) -> list[bytes]:
        wanted = range(first, min(first + count, self.rows))
        found: list[bytes] = []
        if not wanted:
            return found
        with self.path.open("rb") as file:
            left = self.seek(first, file)
            pending = b""
            for line in wanted:
                while b"\n" not in pending and len(pending) < MAX_LINE and left:
                    data = file.read(min(BLOCK, left))
                    left -= len(data)
                    pending += data
                text, newline, pending = pending.partition(b"\n")
                found.append(text[:MAX_LINE])
                if not newline and line + 1 in wanted:
                    left = self.seek(line + 1, file)
        return found
