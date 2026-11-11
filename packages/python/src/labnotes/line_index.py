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
        self.tail_start = 0

    @property
    def rows(self) -> int:
        return self.lines + (self.scanned > self.tail_start)  # probe

    def extend(self) -> bool:
        before = self.scanned
        with self.path.open("rb") as file:
            file.seek(self.scanned)
            while data := file.read(BLOCK - self.scanned % BLOCK):
                if (found := data.rfind(b"\n")) >= 0:
                    self.tail_start = self.scanned + found + 1
                    self.lines += data.count(b"\n")
                self.scanned += len(data)
                if self.scanned % BLOCK == 0:  # probe
                    self.breaks.append(self.lines)
        return self.scanned != before  # probe

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

    def read(self, first: int, count: int) -> list[bytes]:
        last = min(first + count, self.rows)
        found: list[bytes] = []
        if first >= last:
            return found
        with self.path.open("rb") as file:
            position = self.start(first, file)
            file.seek(position)
            pending = b""
            while len(found) < last - first:  # probe
                cut = pending.find(b"\n")
                if cut >= 0:
                    found.append(pending[:cut][:MAX_LINE])
                    pending = pending[cut + 1 :]
                elif len(pending) >= MAX_LINE or position >= self.scanned:  # probe
                    found.append(pending[:MAX_LINE])
                    line = first + len(found)
                    if line >= last:  # probe
                        break  # probe
                    position = self.start(line, file)
                    file.seek(position)
                    pending = b""
                else:
                    data = file.read(min(BLOCK, self.scanned - position))
                    position += len(data)
                    pending += data
        return found
