from typing import TYPE_CHECKING

from labnotes.view.serve import serve

if TYPE_CHECKING:
    from labnotes.view.changed import Changed
    from labnotes.view.daemon import Daemon
    from labnotes.view.experiment import Experiment
    from labnotes.view.selected import Selected

__all__ = ["Changed", "Daemon", "Experiment", "Selected", "serve"]


# Runs-view scripts import this package, so Textual loads only when asked for.
def __getattr__(name: str) -> object:
    if name == "Changed":
        from labnotes.view.changed import Changed

        return Changed
    if name == "Experiment":
        from labnotes.view.experiment import Experiment

        return Experiment
    if name == "Daemon":
        from labnotes.view.daemon import Daemon

        return Daemon
    if name == "Selected":
        from labnotes.view.selected import Selected

        return Selected
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
