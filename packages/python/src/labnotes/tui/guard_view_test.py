import asyncio
from unittest import mock

from textual.app import App, ComposeResult
from textual.color import Color
from textual.widget import Widget
from textual.widgets import Static

from labnotes.tui.guard_view import guard_view


class Shown(Static):
    DEFAULT_CSS = "Shown { color: red; }"

    def compose(self) -> ComposeResult:
        yield Static("inside", id="inside")

    def on_mount(self) -> None:
        self.update("mounted")


class Broken(Widget):
    def compose(self) -> ComposeResult:
        yield Static("first", id="first")
        raise RuntimeError("compose broke")


class Raising(Widget):
    def on_mount(self) -> None:
        raise ValueError("mount broke")


def host(widget: Widget) -> App[None]:
    class Host(App[None]):
        def compose(self) -> ComposeResult:
            yield widget

    return Host()


def test_keeps_the_view_s_name_module_and_class() -> None:
    guarded = guard_view(Shown, mock.Mock())

    assert issubclass(guarded, Shown)
    assert guarded.__name__ == "Shown"
    assert guarded.__qualname__ == "Shown"
    assert guarded.__module__ == Shown.__module__


def test_composes_and_mounts_a_view_that_works() -> None:
    failed = mock.Mock()
    view = guard_view(Shown, failed)()

    async def drive() -> None:
        async with host(view).run_test() as pilot:
            await pilot.pause()

            assert view.query_one("#inside", Static).content == "inside"
            assert view.content == "mounted"
            assert view.styles.color == Color.parse("red")

    asyncio.run(drive())
    failed.assert_not_called()


def test_reports_an_error_in_compose_and_keeps_the_app_running() -> None:
    failed = mock.Mock()
    app = host(guard_view(Broken, failed)())

    async def drive() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()

            assert app.is_running

    asyncio.run(drive())
    [[error]] = [call.args for call in failed.call_args_list]
    assert str(error) == "compose broke"
    assert app.return_code is None


def test_reports_an_error_in_a_handler_and_keeps_the_app_running() -> None:
    failed = mock.Mock()
    app = host(guard_view(Raising, failed)())

    async def drive() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()

            assert app.is_running

    asyncio.run(drive())
    [[error]] = [call.args for call in failed.call_args_list]
    assert str(error) == "mount broke"
    assert app.return_code is None
