from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.flash_value import FADE_SECONDS, FRESH_SECONDS, FlashValue


@pytest.fixture
def label() -> Iterator[FlashValue]:
    widget = FlashValue(id="value")
    with (
        mock.patch.object(widget, "update") as update,
        mock.patch.object(widget, "flash") as flash,
        mock.patch("labnotes.tui.flash_value.time.time", return_value=100.0),
    ):
        widget.update = update  # type: ignore[method-assign]
        widget.flash = flash  # type: ignore[method-assign]
        yield widget


def test_shows_the_first_value_without_flashing(label: FlashValue) -> None:
    label.set_value("1 at a time")
    assert label.value == "1 at a time"
    label.update.assert_called_once_with("1 at a time")  # type: ignore[attr-defined]
    label.flash.assert_not_called()  # type: ignore[attr-defined]


def test_flashes_a_live_change(label: FlashValue) -> None:
    label.set_value("1")
    label.set_value("2")
    label.flash.assert_called_once_with()  # type: ignore[attr-defined]
    label.update.assert_called_with("2")  # type: ignore[attr-defined]


def test_ignores_a_repeat_of_the_same_value(label: FlashValue) -> None:
    label.set_value("1")
    label.set_value("1", 100.0)
    label.flash.assert_not_called()  # type: ignore[attr-defined]


def test_flashes_a_change_that_just_happened(label: FlashValue) -> None:
    label.set_value("1")
    label.set_value("2", 100.0 - FRESH_SECONDS + 0.01)
    label.flash.assert_called_once_with()  # type: ignore[attr-defined]


def test_stays_quiet_for_replayed_changes(label: FlashValue) -> None:
    label.set_value("1")
    label.set_value("2", 100.0 - FRESH_SECONDS)
    label.flash.assert_not_called()  # type: ignore[attr-defined]
    assert label.value == "2"


def test_flash_is_tuned_to_about_a_second() -> None:
    assert FRESH_SECONDS == 2.0
    assert FADE_SECONDS == 1.0


@pytest.fixture
def styled() -> Iterator[tuple[FlashValue, mock.Mock, mock.Mock, mock.Mock]]:
    widget = FlashValue()
    styles = mock.Mock(background="normal")
    app = mock.Mock(theme_variables={"warning": "#ffa62b"})
    with (
        mock.patch.object(widget, "styles", new=styles),
        mock.patch.object(FlashValue, "app", new=app),
        mock.patch("labnotes.tui.flash_value.Color") as color,
    ):
        yield widget, styles, app, color


def test_flash_lights_the_warning_color_and_fades_back(
    styled: tuple[FlashValue, mock.Mock, mock.Mock, mock.Mock],
) -> None:
    widget, styles, app, color = styled
    widget.flash()
    styles.clear_rule.assert_called_once_with("background")
    color.parse.assert_called_once_with("#ffa62b")
    assert styles.background is color.parse.return_value
    styles.animate.assert_called_once_with(
        "background",
        "normal",
        duration=FADE_SECONDS,
        level="basic",
        on_complete=widget.settle,
    )


def test_flash_reads_the_css_background_after_clearing_its_own(
    styled: tuple[FlashValue, mock.Mock, mock.Mock, mock.Mock],
) -> None:
    widget, styles, app, color = styled
    styles.background = "mid-flash"
    styles.clear_rule.side_effect = lambda rule: setattr(styles, "background", "css")
    widget.flash()
    assert styles.animate.call_args.args == ("background", "css")


def test_settle_drops_the_inline_background(
    styled: tuple[FlashValue, mock.Mock, mock.Mock, mock.Mock],
) -> None:
    widget, styles, app, color = styled
    widget.settle()
    styles.clear_rule.assert_called_once_with("background")
