import asyncio
import time
from collections.abc import Awaitable, Callable
from unittest import mock

from textual.app import App, ComposeResult
from textual.color import Color

from labnotes.tui.flash_value import FADE_SECONDS, FRESH_SECONDS, FlashValue


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield FlashValue(id="value")


def hosted(check: Callable[[Host, FlashValue], Awaitable[None]]) -> None:
    async def drive() -> None:
        app = Host()
        async with app.run_test():
            await check(app, app.query_one(FlashValue))

    asyncio.run(drive())


def test_shows_the_first_value_without_flashing() -> None:
    async def check(app: Host, label: FlashValue) -> None:
        with mock.patch.object(label, "flash") as flash:
            label.set_value("1 at a time")
        assert label.value == "1 at a time"
        assert "1 at a time" in str(label.render())
        flash.assert_not_called()

    hosted(check)


def test_flashes_a_live_change() -> None:
    async def check(app: Host, label: FlashValue) -> None:
        label.set_value("1")
        with mock.patch.object(label, "flash") as flash:
            label.set_value("2")
        flash.assert_called_once_with()
        assert "2" in str(label.render())

    hosted(check)


def test_ignores_a_repeat_of_the_same_value() -> None:
    async def check(app: Host, label: FlashValue) -> None:
        label.set_value("1")
        with mock.patch.object(label, "flash") as flash:
            label.set_value("1", time.time())
        flash.assert_not_called()

    hosted(check)


def test_flashes_a_change_that_just_happened() -> None:
    async def check(app: Host, label: FlashValue) -> None:
        label.set_value("1")
        with (
            mock.patch.object(label, "flash") as flash,
            mock.patch("labnotes.tui.flash_value.time.time", return_value=100.0),
        ):
            label.set_value("2", 100.0 - FRESH_SECONDS + 0.01)
        flash.assert_called_once_with()

    hosted(check)


def test_stays_quiet_for_replayed_changes() -> None:
    async def check(app: Host, label: FlashValue) -> None:
        label.set_value("1")
        with (
            mock.patch.object(label, "flash") as flash,
            mock.patch("labnotes.tui.flash_value.time.time", return_value=100.0),
        ):
            label.set_value("2", 100.0 - FRESH_SECONDS)
        flash.assert_not_called()
        assert label.value == "2"

    hosted(check)


def test_flash_is_tuned_to_about_a_second() -> None:
    assert FRESH_SECONDS == 2.0
    assert FADE_SECONDS == 1.0


def test_flash_lights_the_warning_color_and_fades_back() -> None:
    async def check(app: Host, label: FlashValue) -> None:
        normal = label.styles.background
        with mock.patch.object(label.styles, "animate") as animate:
            label.flash()
        assert label.styles.background == Color.parse(app.theme_variables["warning"])
        animate.assert_called_once_with(
            "background",
            normal,
            duration=FADE_SECONDS,
            level="basic",
            on_complete=label.settle,
        )
        label.settle()
        assert not label.styles.inline.has_rule("background")

    hosted(check)


def test_flash_again_fades_to_the_css_background() -> None:
    async def check(app: Host, label: FlashValue) -> None:
        normal = label.styles.background
        label.flash()
        with mock.patch.object(label.styles, "animate") as animate:
            label.flash()
        assert animate.call_args.args == ("background", normal)

    hosted(check)
