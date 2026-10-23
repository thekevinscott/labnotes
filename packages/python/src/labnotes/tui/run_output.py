import codecs
from pathlib import Path
from typing import Any, Self

from rich.text import Text
from textual.geometry import Size
from textual.widgets import RichLog

STREAMS = ("stdout", "stderr")


class RunOutput(RichLog):
    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id, wrap=True, min_width=1)
        self.reset()

    def reset(self) -> None:
        self.offsets = dict.fromkeys(STREAMS, 0)
        self.decoders = {
            stream: codecs.getincrementaldecoder("utf-8")(errors="replace")
            for stream in STREAMS
        }
        self.last_stream: str | None = None
        self.unfinished = ""
        self.written_rows = 0
        self.clear()
        # A hidden log has no width; writing now would wrap every line to one
        # cell. Hold writes until it's shown and resized.
        self._size_known = self.scrollable_content_region.width > 0

    @property
    def mid_line(self) -> bool:
        return bool(self.unfinished)

    def follow(self, folder: Path) -> None:
        for stream in STREAMS:
            path = folder / f"{stream}.log"
            if not path.exists():
                continue
            with path.open("rb") as log:
                log.seek(self.offsets[stream])
                data = log.read()
            self.offsets[stream] += len(data)
            text = self.decoders[stream].decode(data)
            if not text:
                continue
            # A stream's unfinished line is redrawn as it grows, but the
            # other stream's output starts below it.
            if self.mid_line and stream == self.last_stream:
                self.drop_unfinished()
                text = self.unfinished + text
            *complete, self.unfinished = text.split("\n")
            if complete:
                self.write(Text.from_ansi("\n".join(complete)))
            if self.unfinished:
                self.write(Text.from_ansi(self.unfinished))
            self.last_stream = stream

    # Counted here, not in follow: writes made before the size is known
    # render later, from on_resize.
    def write(self, content: object, *args: Any, **kwargs: Any) -> Self:
        rows = len(self.lines)
        super().write(content, *args, **kwargs)
        self.written_rows = len(self.lines) - rows
        return self

    def drop_unfinished(self) -> None:
        if not self._size_known:
            self._deferred_renders.pop()
            return
        del self.lines[-self.written_rows :]
        self._line_cache.clear()
        self.virtual_size = Size(self.virtual_size.width, len(self.lines))
        self.refresh()
