from importlib import import_module

import pytest

view = import_module("labnotes.view")


def test_exports_the_view_contract() -> None:
    assert view.__all__ == [
        "Changed",
        "Experiment",
        "Restart",
        "Select",
        "Selected",
        "Stop",
        "serve",
    ]
    for name in view.__all__[:-1]:
        assert getattr(view, name).__name__ == name


def test_unknown_export_names_it() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'missing'"):
        getattr(view, "missing")


@pytest.mark.parametrize("name", ["A", "D", "Z"])
def test_names_on_either_side_of_an_export_are_unknown(name: str) -> None:
    with pytest.raises(AttributeError):
        getattr(view, name)


def test_matches_an_export_by_value() -> None:
    assert getattr(view, "".join(["Chan", "ged"])).__name__ == "Changed"
    assert getattr(view, "".join(["Experi", "ment"])).__name__ == "Experiment"


def test_imports_the_contract_only_when_asked() -> None:
    for name in view.__all__[:-1]:
        assert name not in vars(view)
