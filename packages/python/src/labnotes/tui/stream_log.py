import codecs
from collections.abc import Iterable
from pathlib import Path
from typing import Self

from rich.ansi import re_ansi
from rich.text import Text
from rich.cells import cell_len
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.strip import Strip

from labnotes.latest_log import latest_log


class StreamLog(ScrollView):
    DEFAULT_CSS = """
    StreamLog {
        background: $surface;
        color: $text;
        overflow: scroll;
        &:focus { background-tint: $foreground 5%; }
    }
    """

    def __init__(self, stream: str, id: str | None = None) -> None:
        super().__init__(id=id)
        self.stream = stream
        self.auto_scroll = True
        self._lines: list[str] = []
        self._line_widths: list[int] = []
        self._line_cache: dict[int, Strip] = {}
        self._width = 0
        self.reset()

    @property
    def lines(self) -> list[str]:
        return self._lines

    @property
    def count(self) -> int:
        return len(self._lines) - self.mid_line

    def clear(self) -> Self:
        self._lines.clear()
        self._line_widths.clear()
        self._line_cache.clear()
        self._width = 0
        self.virtual_size = Size(0, 0)
        self.refresh()
        return self

    def reset(self) -> None:
        self.read_to = 0
        self.path: Path | None = None
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.unfinished = ""
        self.clear()

    @property
    def mid_line(self) -> bool:
        return bool(self.unfinished)

    def follow(self, folder: Path) -> None:
        path = latest_log(folder, self.stream)
        if path == self.path and (
            not path.exists() or path.stat().st_size < self.read_to
        ):
            self.reset()
        if not path.exists():
            return
        if path != self.path:
            self.path = path
            self.read_to = 0
        with path.open("rb") as log:
            log.seek(self.read_to)
            data = log.read()
        self.read_to += len(data)
        text = self.decoder.decode(data)
        if not text:
            return
        if self.mid_line:
            self.drop_unfinished()
            text = self.unfinished + text
        *complete, self.unfinished = text.split("\n")
        if complete:
            self.write_lines(complete)
        if self.unfinished:
            self.write_lines([self.unfinished])

    def write_lines(self, lines: Iterable[str], scroll_end: bool | None = None) -> Self:
        new_lines = list(lines)
        if not new_lines:
            return self
        at_end = self.is_vertical_scroll_end
        self._lines.extend(new_lines)
        widths = [
            cell_len(re_ansi.sub("", line.rsplit("\r", 1)[-1])) for line in new_lines
        ]
        self._line_widths.extend(widths)
        self._width = max(self._width, *widths)
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
        removed_width = self._line_widths.pop()
        if removed_width == self._width:
            self._width = max(self._line_widths, default=0)
        self._line_cache.pop(len(self._lines), None)
        self.virtual_size = Size(self._width, len(self._lines))
        self.refresh()

    def render_line(self, y: int) -> Strip:
        """Render only the visible line, keeping the uncropped result cached."""
        scroll_x, scroll_y = self.scroll_offset
        row = scroll_y + y
        rich_style = self.rich_style
        if row >= len(self._lines):
            return Strip.blank(self.size.width, rich_style)
        selection = self.text_selection
        if selection is None and row in self._line_cache:
            line = self._line_cache[row]
        else:
            line_text = Text.from_ansi(self._lines[row], style=rich_style)
            if selection is not None and (span := selection.get_span(row)) is not None:
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
                self._line_cache[row] = line
        return line.crop_extend(
            scroll_x, scroll_x + self.size.width, rich_style
        ).apply_offsets(scroll_x, row)
