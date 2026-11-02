from unittest import mock

from labnotes.tui.guard_view import Widget, guard_view


def test_keeps_the_view_identity() -> None:
    class Example(Widget):
        pass

    guarded = guard_view(Example, mock.Mock())

    assert issubclass(guarded, Example)
    assert guarded.__name__ == Example.__name__
    assert guarded.__module__ == Example.__module__
