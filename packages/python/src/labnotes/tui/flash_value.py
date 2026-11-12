"""Draw the eye to a displayed value when it changes."""

import time

from textual.color import Color
from textual.widgets import Static

FRESH_SECONDS = 2.0
FADE_SECONDS = 1.0


class FlashValue(Static):
    """Flash only live changes, so first draws and journal replays stay quiet."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.value: str | None = None

    def set_value(self, value: str, at: float | None = None) -> None:
        """Show a value; `at` is the event's wall-clock time, if it has one."""
        changed = self.value is not None and value != self.value
        self.value = value
        self.update(value)
        if changed and (at is None or time.time() - at < FRESH_SECONDS):
            self.flash()

    def flash(self) -> None:
        self.styles.clear_rule("background")
        normal = self.styles.background
        self.styles.background = Color.parse(self.app.theme_variables["warning"])
        self.styles.animate(
            "background",
            normal,
            duration=FADE_SECONDS,
            level="basic",
            on_complete=self.settle,
        )

    def settle(self) -> None:
        self.styles.clear_rule("background")
