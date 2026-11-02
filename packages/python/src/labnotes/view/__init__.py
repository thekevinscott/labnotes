from typing import TYPE_CHECKING

from labnotes.view.experiment import Experiment
from labnotes.view.serve import serve

if TYPE_CHECKING:
    from labnotes.view.changed import Changed

__all__ = ["Changed", "Experiment", "serve"]


# Runs-view scripts import this package, so Textual loads only when asked for.
def __getattr__(name: str) -> object:
    if name == "Changed":
        from labnotes.view.changed import Changed

        return Changed
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
