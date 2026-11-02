from typing import TYPE_CHECKING

from labnotes.view.serve import serve

if TYPE_CHECKING:
    from labnotes.view.changed import Changed
    from labnotes.view.experiment import Experiment

__all__ = ["Changed", "Experiment", "serve"]


# Runs-view scripts import this package, so Textual loads only when asked for.
def __getattr__(name: str) -> object:
    if name == "Changed":
        from labnotes.view.changed import Changed

        return Changed
    if name == "Experiment":
        from labnotes.view.experiment import Experiment

        return Experiment
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
