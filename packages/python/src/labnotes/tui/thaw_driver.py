"""Terminal driver that survives a bare SIGSTOP and SIGCONT."""

from typing import Any

from textual.drivers.linux_driver import LinuxDriver


class ThawDriver(LinuxDriver):
    """Textual's SIGCONT handler assumes SIGTSTP already left application mode.
    A bare SIGSTOP doesn't, so each thaw stacked an input thread that could
    outlive Ctrl-C. Re-entering the alternate screen clears it; repaint.
    """

    def _sigcont_application(self, *_: Any) -> None:
        if not self._auto_restart or self._must_signal_resume:
            super()._sigcont_application()
            return
        self.stop_application_mode()
        self.close()
        self.start_application_mode()
        self._loop.call_soon_threadsafe(self._app.refresh)
