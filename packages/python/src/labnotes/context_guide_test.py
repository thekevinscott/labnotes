from importlib.metadata import version
from importlib.resources import files

from labnotes.context_guide import context_guide


def test_the_first_line_names_the_installed_version() -> None:
    assert context_guide().splitlines()[0] == f"labnotes {version('labnotes')}"


def test_prints_the_whole_guide_after_a_blank_line() -> None:
    guide = files("labnotes").joinpath("context.md").read_text(encoding="utf-8")
    assert context_guide() == f"labnotes {version('labnotes')}\n\n{guide}"


def test_the_guide_starts_with_usage() -> None:
    assert context_guide().splitlines()[2] == "## Usage"
