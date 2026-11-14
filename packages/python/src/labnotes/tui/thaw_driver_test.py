import asyncio
from collections.abc import Callable
from unittest import mock

from labnotes.tui.thaw_driver import ThawDriver


def signals(send: Callable[[ThawDriver], None]) -> list[object]:
    calls = mock.Mock()

    async def run() -> None:
        with mock.patch("textual.drivers.linux_driver.signal.signal"):
            driver = ThawDriver(calls.app)
        with (
            mock.patch.object(driver, "stop_application_mode", calls.stop),
            mock.patch.object(driver, "start_application_mode", calls.start),
            mock.patch.object(driver, "close", calls.close),
            mock.patch("textual.drivers.linux_driver.os.kill"),
        ):
            send(driver)
            await asyncio.sleep(0)

    asyncio.run(run())
    return list(calls.mock_calls)


def test_thaw_after_a_bare_stop_restarts_application_mode_and_repaints() -> None:
    assert signals(lambda driver: driver._sigcont_application()) == [
        mock.call.stop(),
        mock.call.close(),
        mock.call.start(),
        mock.call.app.refresh(),
    ]


def test_thaw_after_ctrl_z_only_resumes() -> None:
    def suspend_then_thaw(driver: ThawDriver) -> None:
        driver._sigtstp_application()
        driver._sigcont_application()

    assert signals(suspend_then_thaw) == [
        mock.call.stop(),
        mock.call.close(),
        mock.call.start(),
    ]


def test_thaw_without_auto_restart_leaves_the_terminal_alone() -> None:
    def thaw_unmanaged(driver: ThawDriver) -> None:
        with driver.no_automatic_restart():
            driver._sigcont_application()

    assert signals(thaw_unmanaged) == []
