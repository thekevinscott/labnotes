"""Terminal driver that survives a bare SIGSTOP and SIGCONT."""

from typing import Any

from textual.drivers.linux_driver import LinuxDriver


class ThawDriver(LinuxDriver):
    """Textual's SIGCONT handler re-enters application mode, assuming SIGTSTP
    left it. A bare SIGSTOP runs no handler, so each thaw stacked an input
    thread that could outlive Ctrl-C and kept raw mode as the mode to restore.
    Closing joins the old writer so its restore output lands before the new
    writer's; re-entering the alternate screen clears it, hence the repaint.
    """

    def _sigcont_application(self, *_: Any) -> None:
        if not self._auto_restart or self._must_signal_resume:
            super()._sigcont_application()
            return
        self.stop_application_mode()
        self.close()
        self.start_application_mode()
        self._loop.call_soon_threadsafe(self._app.refresh)
