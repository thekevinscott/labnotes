from pathlib import Path

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.selection import Selection
from textual.strip import Strip

from labnotes.latest_log import latest_log
from labnotes.line_index import LineIndex
from labnotes.visible_line import visible_line

BUFFER = 100


class StreamLog(ScrollView):
    """Follow one stream's logs, reading only the lines on screen.

    Long lines wrap, so a log line can take several screen rows. Scrolling
    moves one log line at a time: `scroll_y` is the top line, except at the
    end, where the last lines sit against the bottom edge.
    """

    DEFAULT_CSS = """
    StreamLog {
        background: $surface;
        color: $text;
        overflow-x: hidden;
        overflow-y: scroll;
        &:focus { background-tint: $foreground 5%; }
    }
    """

    def __init__(self, stream: str, id: str | None = None) -> None:
        super().__init__(id=id)
        self.stream = stream
        self.pinned = True
        self.reset()

    def reset(self) -> None:
        self.segments: list[LineIndex] = []
        self.first = 0
        self.window: list[str] = []
        self.wrapped: dict[int, list[Strip]] = {}
        self.shown: tuple[object, list[Strip]] = (None, [])
        self.bottom = 0
        self.virtual_size = Size(0, 0)
        self.refresh()

    @property
    def view(self) -> Size:
        return self.scrollable_content_region.size

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
        if not self.segments[-1].extend():
            return
        del self.window[max(0, settled - self.first) :]
        for line in [line for line in self.wrapped if line >= settled]:
            del self.wrapped[line]
        self.settle()

    def settle(self) -> None:
        """Size the scroll range so the last line can reach the bottom edge."""
        self.shown = (None, [])
        height = self.view.height
        if not self.view.width or not height:
            self.bottom = self.rows
            self.virtual_size = Size(0, self.rows)
            return
        line, filled = self.rows, 0
        while line > 0 and filled < height:
            line -= 1
            filled += len(self.wrap(line))
        self.bottom = line
        self.virtual_size = Size(0, line + height)
        self.refresh()
        if self.pinned:
            self.scroll_to(y=line, animate=False, immediate=True)

    def on_resize(self, event: events.Resize) -> None:
        self.wrapped.clear()
        self.settle()

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        self.pinned = round(new_value) >= self.bottom

    def selection_updated(self, selection: Selection | None) -> None:
        self.wrapped.clear()
        self.shown = (None, [])
        super().selection_updated(selection)

    def read(self, first: int, count: int) -> list[str]:
        found: list[str] = []
        for segment in self.segments:
            if first >= segment.rows:
                first -= segment.rows
                continue
            lines = segment.read(first, count - len(found))
            found.extend(
                visible_line(line.decode("utf-8", "replace")) for line in lines
            )
            first = 0
        return found

    def line(self, line: int) -> str:
        if not self.first <= line < self.first + len(self.window):
            self.first = max(0, line - BUFFER)
            self.window = self.read(self.first, self.view.height + 2 * BUFFER)
            # Keep the tail too: following the log wraps it on every write.
            tail = self.rows - self.view.height
            self.wrapped = {
                kept: strips
                for kept, strips in self.wrapped.items()
                if kept >= tail or self.first <= kept < self.first + len(self.window)
            }
        return self.window[line - self.first]

    def wrap(self, line: int) -> list[Strip]:
        """Cut one log line into screen rows, keeping offsets for selection."""
        if (strips := self.wrapped.get(line)) is not None:
            return strips
        width = self.view.width
        text = Text.from_ansi(self.line(line), style=self.rich_style)
        selection = self.text_selection
        if selection is not None and (span := selection.get_span(line)) is not None:
            start, end = span
            text.stylize(
                self.screen.get_component_rich_style("screen--selection"),
                start,
                len(text) if end == -1 else end,
            )
        strip = Strip(text.render(self.app.console), cell_len(text.plain))
        length = strip.cell_length
        pieces = (
            strip.divide([*range(width, length, width), length]) if length else [strip]
        )
        strips, offset = [], 0
        for piece in pieces:
            strips.append(
                piece.extend_cell_length(width, self.rich_style).apply_offsets(
                    offset, line
                )
            )
            offset += sum(len(segment.text) for segment in piece)
        self.wrapped[line] = strips
        return strips

    def screen_rows(self) -> list[Strip]:
        top = round(self.scroll_y)
        key = (top, self.view, self.rows, self.bottom)
        if self.shown[0] == key:
            return self.shown[1]
        height = self.view.height
        found: list[Strip] = []
        line = top
        while line < self.rows and (top >= self.bottom or len(found) < height):
            found.extend(self.wrap(line))
            line += 1
        found = found[-height:] if top >= self.bottom else found[:height]
        self.shown = (key, found)
        return found

    def render_line(self, y: int) -> Strip:
        found = self.screen_rows()
        if y < len(found):
            return found[y]
        return Strip.blank(self.view.width, self.rich_style)
