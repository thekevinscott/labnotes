import traceback
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Static

from labnotes.tui.guard_view import guard_view
from labnotes.tui.load_view import load_view
from labnotes.view.changed import Changed
from labnotes.view.experiment import Experiment


def failure(name: str, error: Exception) -> Static:
    text = "".join(traceback.format_exception(error))
    return Static(f"The {name} view failed.\n\n{text}", markup=False, classes="failure")


class ViewPane(Container):
    """Hold one view, and its error in its place if it fails."""

    DEFAULT_CSS = """
    ViewPane { height: 1fr; }
    ViewPane > .failure { color: $text-error; }
    """

    def __init__(self, name: str, spec: str, root: Path, id: str) -> None:
        super().__init__(id=id)
        self.view_name = name
        self.spec = spec
        self.root = root
        self.view: Widget | None = None

    def compose(self) -> ComposeResult:
        try:
            self.view = guard_view(load_view(self.spec, self.root), self.fail)()
        except Exception as error:
            yield failure(self.view_name, error)
            return
        yield self.view

    def fail(self, error: Exception) -> None:
        if self.view is None:
            return
        self.view = None
        self.remove_children()
        self.mount(failure(self.view_name, error))

    def deliver(
        self, experiment: Experiment | None, paths: frozenset[str] = frozenset()
    ) -> None:
        if self.view is not None:
            self.view.post_message(Changed(experiment, paths))
