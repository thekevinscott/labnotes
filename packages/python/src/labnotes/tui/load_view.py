import importlib
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType

from textual.widget import Widget


def load_view(spec: str, root: Path) -> type[Widget]:
    """Import the widget class `spec` names: `file.py:Class` from `root`, or `module:Class`."""
    source, _, name = spec.rpartition(":")
    if source.endswith(".py"):
        path = root / source
        module = ModuleType(f"labnotes_view_{path.stem}")
        module.__file__ = str(path)
        # Dataclasses and pickling look a class's module up by name.
        sys.modules[module.__name__] = module
        SourceFileLoader(module.__name__, str(path)).exec_module(module)
    else:
        module = importlib.import_module(source)
    view = getattr(module, name, None)
    if view is None:
        raise ImportError(f"{source} has no {name}")
    if not isinstance(view, type) or not issubclass(view, Widget):
        raise TypeError(f"{spec} is not a Textual widget")
    return view
