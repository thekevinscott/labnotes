import asyncio
from unittest import mock

from labnotes.tui.guard_view import Widget, guard_view


def test_keeps_the_view_identity() -> None:
    class Example(Widget):
        pass

    guarded = guard_view(Example, mock.Mock())

    assert issubclass(guarded, Example)
    assert guarded.__name__ == Example.__name__
    assert guarded.__module__ == Example.__module__


def test_reports_compose_errors() -> None:
    class Example(Widget):
        def compose(self):
            raise ValueError("compose broke")
            yield

    failed = mock.Mock()
    shown = guard_view(Example, failed)()

    assert list(shown.compose()) == []
    assert str(failed.call_args.args[0]) == "compose broke"


def test_reports_handler_errors() -> None:
    class Example(Widget):
        async def _dispatch_message(self, message):
            raise ValueError("handler broke")

    failed = mock.Mock()
    shown = guard_view(Example, failed)()

    asyncio.run(shown._dispatch_message(mock.Mock()))

    assert str(failed.call_args.args[0]) == "handler broke"
