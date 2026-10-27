from pathlib import Path

import pytest
from conftest import write

from labnotes.cli import main

COMMAND = """command = "sh -c 'echo run $2 >> journal.txt' sh"
[params]
m = ["a", "b"]
"""


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


def make_project(root: Path, shared: str = "", own: str = "") -> Path:
    write(
        root / ".labnotes.toml",
        f'[experiments]\npath = "{{experiment}}"\n[experiment]\n{shared}',
    )
    write(root / "exp" / "experiment.toml", own + COMMAND)
    return root


def journal(root: Path) -> list[str]:
    return (root / "journal.txt").read_text().splitlines()


def test_wraps_the_runs_in_the_projects_setup_and_teardown(tmp_path: Path) -> None:
    root = make_project(
        tmp_path,
        shared='setup = "echo up >> journal.txt"\n'
        'teardown = "echo down >> journal.txt"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    assert journal(root) == ["up", "run a", "run b", "down"]


def test_prefers_the_experiments_setup_and_then_the_flags(tmp_path: Path) -> None:
    root = make_project(
        tmp_path,
        shared='setup = "echo shared >> journal.txt"\n'
        'teardown = "echo shared down >> journal.txt"\n',
        own='setup = "echo own >> journal.txt"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) == 0
    assert (
        labnotes(
            root,
            [
                "experiments",
                "exp",
                "run",
                "--teardown",
                "echo flag down >> journal.txt",
            ],
        )
        == 0
    )

    assert journal(root) == [
        *["own", "run a", "run b", "shared down"],
        *["own", "run a", "run b", "flag down"],
    ]


def test_runs_nothing_but_still_tears_down_when_setup_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(
        tmp_path,
        own='setup = "echo no db >&2; exit 4"\n'
        'teardown = "echo down >> journal.txt"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert "setup command echo no db >&2; exit 4 exited 4: no db" in (
        capsys.readouterr().err
    )
    assert journal(root) == ["down"]


def test_fails_the_invocation_when_teardown_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, own='teardown = "exit 5"\n')

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert "teardown command exit 5 exited 5" in capsys.readouterr().err
    assert journal(root) == ["run a", "run b"]
