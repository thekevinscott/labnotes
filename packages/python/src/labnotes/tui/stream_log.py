from pathlib import Path

from rich.ansi import re_ansi
from rich.text import Text
from rich.cells import cell_len
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.strip import Strip

from labnotes.latest_log import latest_log
from labnotes.line_index import LineIndex

BUFFER = 100


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
        self.reset()

    def reset(self) -> None:
        self.segments: list[LineIndex] = []
        self.first = 0
        self.window: list[str] = []
        self._line_cache: dict[int, Strip] = {}
        self._width = 0
        self.virtual_size = Size(0, 0)
        self.refresh()

    @property
    def rows(self) -> int:
        return sum(segment.rows for segment in self.segments)

    @property
    def count(self) -> int:
        if not self.segments:
            return 0
        last = self.segments[-1]
        return self.rows - last.rows + last.lines

    def follow(self, folder: Path) -> None:
        path = latest_log(folder, self.stream)
        if (
            self.segments
            and self.segments[-1].path == path
            and (not path.exists() or path.stat().st_size < self.segments[-1].scanned)
        ):
            self.reset()
        if not path.exists():
            return
        if not self.segments or self.segments[-1].path != path:
            self.segments.append(LineIndex(path))
        settled = self.count
        at_end = self.is_vertical_scroll_end
        if not self.segments[-1].extend():
            return
        del self.window[max(0, settled - self.first) :]
        for row in [row for row in self._line_cache if row >= settled]:
            del self._line_cache[row]
        self.virtual_size = Size(self._width, self.rows)
        self.refresh()
        if self.is_mounted and self.auto_scroll and at_end:
            self.scroll_end(animate=False, immediate=True, x_axis=False)

    def read(self, first: int, count: int) -> list[str]:
        found: list[str] = []
        for segment in self.segments:
            if first >= segment.rows:
                first -= segment.rows
                continue
            lines = segment.read(first, count - len(found))
            found.extend(line.decode("utf-8", "replace") for line in lines)
            first = 0
        return found

    def load(self, row: int) -> None:
        self.first = max(0, row - BUFFER)
        self.window = self.read(self.first, self.size.height + 2 * BUFFER)
        self._line_cache.clear()
        width = max(
            (
                cell_len(re_ansi.sub("", line.rsplit("\r", 1)[-1]))
                for line in self.window
            ),
            default=0,
        )
        if width > self._width:
            self._width = width
            self.call_after_refresh(self.widen)

    def widen(self) -> None:
        self.virtual_size = Size(self._width, self.rows)

    def render_line(self, y: int) -> Strip:
        """Render only the visible line, keeping the uncropped result cached."""
        scroll_x, scroll_y = self.scroll_offset
        row = scroll_y + y
        rich_style = self.rich_style
        if row >= self.rows:
            return Strip.blank(self.size.width, rich_style)
        if not self.first <= row < self.first + len(self.window):
            self.load(row)
        selection = self.text_selection
        if selection is None and row in self._line_cache:
            line = self._line_cache[row]
        else:
            line_text = Text.from_ansi(self.window[row - self.first], style=rich_style)
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
