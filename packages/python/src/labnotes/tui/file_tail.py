import codecs
from pathlib import Path

from textual.widgets import Log

from labnotes.utils.format_bytes import format_bytes
from labnotes.utils.looks_binary import looks_binary

TAIL_BYTES = 64 * 1024
SNIFF_BYTES = 8192
MAX_LINES = 10_000
PROMPT = "Pick a file to follow it."


def read(path: Path, start: int, end: int) -> bytes:
    with path.open("rb") as file:
        file.seek(start)
        return file.read(end - start)


class FileTail(Log):
    """Show the end of one file and follow what is appended to it."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__(max_lines=MAX_LINES, id=id)
        self.reset()

    def reset(self) -> None:
        self.open(None)

    def open(self, path: Path | None) -> None:
        self.path = path
        self.restart()
        if path is None:
            self.write(PROMPT, scroll_end=False)
        else:
            self.follow()

    def restart(self) -> None:
        self.fed = 0
        self.binary: bool | None = None
        self.gone = False
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.clear()

    def follow(self) -> None:
        if self.path is None:
            return
        try:
            self.advance(self.path)
        except FileNotFoundError:
            self.unavailable(f"{self.path.name} is gone.")
        except OSError as error:
            self.unavailable(f"{self.path.name} can't be read: {error.strerror}.")

    def unavailable(self, notice: str) -> None:
        if not self.gone:
            self.restart()
            self.gone = True
            self.write(notice)

    def advance(self, path: Path) -> None:
        size = path.stat().st_size
        if self.gone or size < self.fed:
            self.restart()
        if self.binary is None:
            if not size:
                return
            self.binary = looks_binary(read(path, 0, min(size, SNIFF_BYTES)))
        if self.binary:
            if size != self.fed:
                self.clear()
                self.fed = size
                self.write(f"{path.name} is binary ({format_bytes(size)}), not shown.")
            return
        if size == self.fed:
            return
        if size - self.fed > TAIL_BYTES:
            if self.fed:
                self.restart()
                self.binary = False
            chunk = read(path, size - TAIL_BYTES, size)
            chunk = chunk[chunk.find(b"\n") + 1 :]
        else:
            chunk = read(path, self.fed, size)
        self.fed = size
        self.write(self.decoder.decode(chunk), scroll_end=self.is_vertical_scroll_end)
