import codecs
from collections.abc import Iterable
from pathlib import Path
from typing import Self

from rich.style import Style
from rich.text import Text
from rich.cells import cell_len
from textual.geometry import Size
from textual.strip import Strip
from textual.widgets import Log

from labnotes.latest_log import latest_log

STREAMS = ("stdout", "stderr")


class RunOutput(Log):
    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self.reset()

    def reset(self) -> None:
        self.offsets = dict.fromkeys(STREAMS, 0)
        self.paths: dict[str, Path] = {}
        self.decoders = {
            stream: codecs.getincrementaldecoder("utf-8")(errors="replace")
            for stream in STREAMS
        }
        self.last_stream: str | None = None
        self.unfinished = ""
        self.clear()

    @property
    def mid_line(self) -> bool:
        return bool(self.unfinished)

    def follow(self, folder: Path) -> None:
        for stream in STREAMS:
            path = latest_log(folder, stream)
            if not path.exists():
                continue
            if self.paths.setdefault(stream, path) != path:
                self.paths[stream] = path
                self.offsets[stream] = 0
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
                self.write_lines(complete)
            if self.unfinished:
                self.write_lines([self.unfinished])
            self.last_stream = stream

    def write_lines(self, lines: Iterable[str], scroll_end: bool | None = None) -> Self:
        new_lines = list(lines)
        if not new_lines:
            return self
        at_end = self.is_vertical_scroll_end
        self._lines.extend(new_lines)
        self._width = max(self._width, max(map(len, new_lines)))
        self.virtual_size = Size(self._width, len(self._lines))
        self.refresh()
        if (
            self.is_mounted
            and (self.auto_scroll if scroll_end is None else scroll_end)
            and at_end
        ):
            self.scroll_end(animate=False, immediate=True, x_axis=False)
        return self

    def drop_unfinished(self) -> None:
        self._lines.pop()
        self._render_line_cache.discard(len(self._lines))
        self.virtual_size = Size(self._width, len(self._lines))
        self.refresh()

    def _render_line_strip(self, y: int, rich_style: Style) -> Strip:
        selection = self.text_selection
        if selection is None and y in self._render_line_cache:
            return self._render_line_cache[y]
        line_text = Text.from_ansi(self._lines[y], style=rich_style)
        if selection is not None:
            if (span := selection.get_span(y)) is not None:
                start, end = span
                if end == -1:
                    end = len(line_text)
                line_text.stylize(
                    self.screen.get_component_rich_style("screen--selection"),
                    start,
                    end,
                )
        line = Strip(line_text.render(self.app.console), cell_len(line_text.plain))
        if selection is None:
            self._render_line_cache[y] = line
        return line
