from pathlib import Path
from typing import Self

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import ContentSwitcher, Tab, Tabs

from labnotes.tui.stream_log import StreamLog

STREAMS = ("stdout", "stderr")


class RunOutput(Vertical):
    DEFAULT_CSS = """
    RunOutput { height: 1fr; }
    RunOutput ContentSwitcher, RunOutput StreamLog { height: 1fr; }
    """
    BINDINGS = [Binding("t", "switch", "stdout/stderr")]

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self.current = STREAMS[0]
        self.logs = {stream: StreamLog(stream, id=stream) for stream in STREAMS}
        self.tabs = {stream: Tab(stream, id=f"{stream}-tab") for stream in STREAMS}
        self.relabel()

    def compose(self) -> ComposeResult:
        yield Tabs(*self.tabs.values())
        with ContentSwitcher(initial=self.current):
            yield from self.logs.values()

    def relabel(self) -> None:
        for stream, tab in self.tabs.items():
            label = f"{stream} ({self.logs[stream].count})"
            if tab.label_text != label:
                tab.label = label

    def follow(self, folder: Path) -> None:
        for log in self.logs.values():
            log.follow(folder)
        self.relabel()

    def reset(self) -> None:
        for log in self.logs.values():
            log.reset()
        self.relabel()

    def show(self, stream: str) -> None:
        self.current = stream
        if self.is_mounted:
            self.query_one(ContentSwitcher).current = stream
            self.query_one(Tabs).active = f"{stream}-tab"

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        event.stop()
        for stream, tab in self.tabs.items():
            if tab is event.tab and stream != self.current:
                self.show(stream)

    def action_switch(self) -> None:
        self.show(STREAMS[1 - STREAMS.index(self.current)])
        self.focus()

    def focus(self, scroll_visible: bool = True) -> Self:
        self.logs[self.current].focus(scroll_visible)
        return self
