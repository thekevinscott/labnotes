from importlib import import_module

import pytest

view = import_module("labnotes.view")


def test_exports_the_view_contract() -> None:
    assert view.__all__ == ["Changed", "Experiment", "Group", "serve"]
    assert view.Changed.__name__ == "Changed"
    assert view.Experiment.__name__ == "Experiment"
    assert view.Group.__name__ == "Group"


def test_unknown_export_names_it() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'missing'"):
        getattr(view, "missing")
