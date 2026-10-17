from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from unittest import mock

from labnotes.context_guide import context_guide

GUIDE = files("labnotes").joinpath("context.md").read_text(encoding="utf-8")
CONFIG = mock.Mock(
    path=Path("/p/.labnotes.toml"),
    root=Path("/p"),
    experiments="{experiment}",
    files="{experiment}/files/",
    runs="{experiment}/runs/{run}",
)


def test_the_first_line_names_the_installed_version() -> None:
    assert context_guide(None, Path("/p")).splitlines()[0] == (
        f"labnotes {version('labnotes')}"
    )


def test_names_the_config_and_its_paths_before_the_guide() -> None:
    assert context_guide(CONFIG, Path("/p/a")) == (
        f"labnotes {version('labnotes')}\n\n"
        "Config: /p/.labnotes.toml\n"
        "Root: /p\n"
        "Experiments: {experiment}\n"
        "Files: {experiment}/files/\n"
        "Runs: {experiment}/runs/{run}\n\n"
        f"{GUIDE}"
    )


def test_says_when_the_project_does_not_use_labnotes() -> None:
    assert context_guide(None, Path("/p/a")) == (
        f"labnotes {version('labnotes')}\n\n"
        "No .labnotes.toml in /p/a. If this project uses labnotes, run it"
        " from the folder that holds .labnotes.toml, or pass -c PATH.\n\n"
        f"{GUIDE}"
    )


def test_the_guide_starts_with_usage() -> None:
    assert GUIDE.splitlines()[0] == "## Usage"
