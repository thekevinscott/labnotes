from importlib import import_module
from typing import TYPE_CHECKING

from labnotes.view.serve import serve

if TYPE_CHECKING:
    from labnotes.view.changed import Changed
    from labnotes.view.daemon import Daemon
    from labnotes.view.experiment import Experiment
    from labnotes.view.select import Select
    from labnotes.view.selected import Selected

__all__ = [
    "Changed",
    "Daemon",
    "Experiment",
    "Select",
    "Selected",
    "serve",
]

LAZY = {
    "Changed": "changed",
    "Daemon": "daemon",
    "Experiment": "experiment",
    "Select": "select",
    "Selected": "selected",
}


# Runs-view scripts import this package, so Textual loads only when asked for.
def __getattr__(name: str) -> object:
    if name not in LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(f"labnotes.view.{LAZY[name]}"), name)
