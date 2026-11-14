import asyncio
from unittest import mock

from labnotes.daemon.quiet_late_wakeup import quiet_late_wakeup


def test_a_late_wakeup_is_dropped_and_other_errors_reach_the_default() -> None:
    loop = mock.Mock()
    quiet_late_wakeup(loop, {"exception": asyncio.InvalidStateError("invalid state")})
    loop.default_exception_handler.assert_not_called()
    other = {"exception": RuntimeError("boom")}
    quiet_late_wakeup(loop, other)
    loop.default_exception_handler.assert_called_once_with(other)
