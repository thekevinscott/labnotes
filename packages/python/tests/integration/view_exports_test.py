import subprocess
import sys

import pytest

from labnotes import view
from labnotes.view.changed import Changed
from labnotes.view.experiment import Experiment
from labnotes.view.group import Group


def test_is_exported_from_the_view_package() -> None:
    assert view.Changed is Changed
    assert view.Experiment is Experiment
    assert view.Group is Group
    assert view.__all__ == ["Changed", "Experiment", "Group", "serve"]


def test_the_view_package_names_what_it_lacks() -> None:
    with pytest.raises(AttributeError, match="'labnotes.view' has no attribute 'nope'"):
        getattr(view, "nope")


def test_importing_the_view_package_leaves_textual_unloaded() -> None:
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            "import labnotes.view, sys; print('textual' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert loaded.stdout == "False\n"
