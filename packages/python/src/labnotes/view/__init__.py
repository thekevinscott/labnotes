from importlib import import_module
from typing import TYPE_CHECKING

from labnotes.view.serve import serve

if TYPE_CHECKING:
    from labnotes.view.changed import Changed
    from labnotes.view.experiment import Experiment
    from labnotes.view.restart import Restart
    from labnotes.view.select import Select
    from labnotes.view.selected import Selected
    from labnotes.view.stop import Stop

__all__ = [
    "Changed",
    "Experiment",
    "Restart",
    "Select",
    "Selected",
    "Stop",
    "serve",
]

LAZY = {
    "Changed": "changed",
    "Experiment": "experiment",
    "Restart": "restart",
    "Select": "select",
    "Selected": "selected",
    "Stop": "stop",
}


# Runs-view scripts import this package, so Textual loads only when asked for.
def __getattr__(name: str) -> object:
    if name not in LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(f"labnotes.view.{LAZY[name]}"), name)
