from collections.abc import Callable, Iterable
from typing import cast

from textual.message import Message
from textual.widget import Widget


def guard_view(view: type[Widget], failed: Callable[[Exception], None]) -> type[Widget]:
    """Subclass a view so errors in its compose and handlers reach `failed`.

    Textual ends the app on any error a widget raises. A view is someone else's
    code, so its errors stay in its pane instead.
    """

    def compose(self: Widget) -> Iterable[Widget]:
        try:
            yield from view.compose(self)
        except Exception as error:
            failed(error)

    # _dispatch_message is private to Textual, but every handler runs under it.
    async def _dispatch_message(self: Widget, message: Message) -> None:
        try:
            await view._dispatch_message(self, message)
        except Exception as error:
            failed(error)

    namespace = {
        "__module__": view.__module__,
        "__qualname__": view.__qualname__,
        "compose": compose,
        "_dispatch_message": _dispatch_message,
    }
    # type() builds a subclass of view, so it is a Widget subclass.
    return cast(type[Widget], type(view.__name__, (view,), namespace))
