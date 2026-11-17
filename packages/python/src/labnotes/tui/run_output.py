from pathlib import Path
from typing import Self

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import ContentSwitcher, Tab, Tabs

from labnotes.tui.run_files import RunFiles
from labnotes.tui.stream_log import StreamLog

STREAMS = ("stdout", "stderr")


class RunOutput(Vertical):
    DEFAULT_CSS = """
    RunOutput { height: 1fr; }
    RunOutput ContentSwitcher, RunOutput StreamLog { height: 1fr; }
    """
    BINDINGS = [Binding("t", "switch", "Next tab")]

    def __init__(self, id: str | None = None, files: bool = False) -> None:
        super().__init__(id=id)
        self.current = STREAMS[0]
        self.logs = {stream: StreamLog(stream, id=stream) for stream in STREAMS}
        self.files = RunFiles(id="files") if files else None
        self.panes = [*STREAMS, *(["files"] if files else [])]
        self.tabs = {pane: Tab(pane, id=f"{pane}-tab") for pane in self.panes}
        self.relabel()

    def compose(self) -> ComposeResult:
        yield Tabs(*self.tabs.values())
        with ContentSwitcher(initial=self.current):
            yield from self.logs.values()
            if self.files is not None:
                yield self.files

    def relabel(self) -> None:
        counts = {stream: log.count for stream, log in self.logs.items()}
        if self.files is not None:
            counts["files"] = self.files.count
        for pane, tab in self.tabs.items():
            label = f"{pane} ({counts[pane]})"
            if tab.label_text != label:
                tab.label = label

    def follow(self, folder: Path) -> None:
        for log in self.logs.values():
            log.follow(folder)
        if self.files is not None:
            self.files.follow(folder)
        self.relabel()

    def reset(self) -> None:
        for log in self.logs.values():
            log.reset()
        if self.files is not None:
            self.files.reset()
        self.relabel()

    def show(self, pane: str) -> None:
        self.current = pane
        if self.is_mounted:
            self.query_one(ContentSwitcher).current = pane
            self.query_one(Tabs).active = f"{pane}-tab"

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        event.stop()
        pane = str(event.tab.id).removesuffix("-tab")
        if pane != self.current:
            self.show(pane)

    def action_switch(self) -> None:
        self.show(self.panes[(self.panes.index(self.current) + 1) % len(self.panes)])
        self.focus()

    def focus(self, scroll_visible: bool = True) -> Self:
        if self.current == "files" and self.files is not None:
            self.files.focus(scroll_visible)
        else:
            self.logs[self.current].focus(scroll_visible)
        return self
