from collections.abc import Mapping
from pathlib import Path

from textual.widget import Widget
from textual.widgets import ContentSwitcher

from labnotes.tui.view_pane import ViewPane
from labnotes.view.experiment import Experiment

MAX_VIEWS = 8


class ViewSwitcher:
    """Mount and switch the same view panes in browse and run screens."""

    left: dict[str, Widget]

    async def add_views(self, specs: Mapping[str, str], root: Path) -> None:
        names = list(specs)[:MAX_VIEWS]
        if not names:
            return
        panes = [
            ViewPane(name, specs[name], root, id=f"view-{number}")
            for number, name in enumerate(names, 2)
        ]
        for pane in panes:
            pane.display = False
        await self.query_one(ContentSwitcher).mount_all(panes)  # type: ignore[attr-defined]
        for number, name in enumerate(["runs", *names], 1):
            self._bindings.bind(str(number), f"show_view({number})", name)  # type: ignore[attr-defined]
        self._bindings.bind("0", "show_view(1)")  # type: ignore[attr-defined]
        self.refresh_bindings()  # type: ignore[attr-defined]

    def deliver(
        self, experiment: Experiment | None, paths: frozenset[str] = frozenset()
    ) -> None:
        for pane in self.query(ViewPane):  # type: ignore[attr-defined]
            pane.deliver(experiment, paths)

    def action_show_view(self, number: int) -> None:
        switcher = self.query_one(ContentSwitcher)  # type: ignore[attr-defined]
        if switcher.current is not None and self.focused is not None:  # type: ignore[attr-defined]
            self.left[switcher.current] = self.focused  # type: ignore[attr-defined]
        switcher.current = f"view-{number}"
        self.call_after_refresh(self.refocus, switcher.current)  # type: ignore[attr-defined]

    def refocus(self, current: str) -> None:
        widget = self.left.get(current)
        if widget is not None and widget.focusable:
            widget.focus()
            return
        self.set_focus(None)  # type: ignore[attr-defined]
        self.screen.focus_next()  # type: ignore[attr-defined]
