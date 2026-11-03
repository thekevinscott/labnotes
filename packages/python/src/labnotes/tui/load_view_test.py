import sys
from pathlib import Path

import pytest

from labnotes.tui.load_view import load_view


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_imports_a_class_from_a_file_under_the_root(tmp_path: Path) -> None:
    write(
        tmp_path / "views/progress.py",
        "from dataclasses import dataclass\n\nfrom textual.widgets import Static\n\n\n"
        "@dataclass\nclass Point:\n    x: 'int'\n\n\nclass Progress(Static):\n    pass\n",
    )

    view = load_view("views/progress.py:Progress", tmp_path)

    assert view.__name__ == "Progress"
    assert view.__module__ == "labnotes_view_progress"


def test_imports_a_class_from_a_module() -> None:
    loaded = load_view("labnotes.tui.runs_table:RunsTable", Path("/nowhere"))
    assert loaded.__module__ == "labnotes.tui.runs_table"
    assert loaded.__name__ == "RunsTable"


def test_names_a_class_the_file_lacks(tmp_path: Path) -> None:
    write(tmp_path / "views/progress.py", "")

    with pytest.raises(ImportError, match="^views/progress.py has no Missing$"):
        load_view("views/progress.py:Missing", tmp_path)


def test_rejects_what_is_not_a_widget(tmp_path: Path) -> None:
    write(tmp_path / "v.py", "class Plain:\n    pass\n\nvalue = 1\n")

    with pytest.raises(TypeError, match="^v.py:Plain is not a Textual widget$"):
        load_view("v.py:Plain", tmp_path)
    with pytest.raises(TypeError, match="^v.py:value is not a Textual widget$"):
        load_view("v.py:value", tmp_path)


def test_raises_what_the_file_raises(tmp_path: Path) -> None:
    write(tmp_path / "v.py", "raise RuntimeError('broken view')\n")

    with pytest.raises(RuntimeError, match="broken view"):
        load_view("v.py:View", tmp_path)


def test_fails_on_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_view("absent.py:View", tmp_path)


def test_keeps_the_file_in_its_module(tmp_path: Path) -> None:
    write(
        tmp_path / "v.py",
        "from textual.widget import Widget\n\nclass V(Widget):\n    pass\n",
    )

    view = load_view("v.py:V", tmp_path)

    assert sys.modules["labnotes_view_v"].__file__ == str(tmp_path / "v.py")
    assert sys.modules["labnotes_view_v"].V is view
