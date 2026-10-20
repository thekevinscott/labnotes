from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.run_control import run_control


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.run_control.load_config") as load_config,
        mock.patch(
            "labnotes.run_control.control_run", new=mock.AsyncMock(return_value=None)
        ) as control_run,
    ):
        yield {"load_config": load_config, "control_run": control_run}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        run_control.main(argv, prog_name="control")
    return exit_info.value.code


@pytest.mark.parametrize(
    ("argv", "args"),
    [
        (["exp", "kill", "exp/r1"], ["exp/r1"]),
        (["exp", "set_concurrency", "3"], [3]),
        (["exp", "move", "exp/r1", "2"], ["exp/r1", 2]),
        (["exp", "interrupt"], []),
    ],
)
def test_sends_the_control(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    argv: list[str],
    args: list[object],
) -> None:
    assert run(argv) == 0

    collaborators["control_run"].assert_awaited_once_with(
        collaborators["load_config"].return_value.root, "exp", argv[1], args
    )
    assert capsys.readouterr().out == ""


def test_says_why_the_daemon_refused(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["control_run"].return_value = "Nothing is running."

    assert run(["exp", "finish"]) == 1

    assert capsys.readouterr().err == "Error: Nothing is running.\n"


@pytest.mark.parametrize(
    ("argv", "said"),
    [
        (["exp", "kill"], "kill takes 1 argument(s)."),
        (["exp", "finish", "extra"], "finish takes 0 argument(s)."),
        (["exp", "set_concurrency", "lots"], "set_concurrency takes a number."),
        (["exp", "move", "exp/r1"], "move takes 2 argument(s)."),
    ],
)
def test_refuses_the_wrong_arguments(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    argv: list[str],
    said: str,
) -> None:
    assert run(argv) == 2

    assert said in capsys.readouterr().err
    collaborators["control_run"].assert_not_awaited()


def test_refuses_an_unknown_action(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["exp", "explode"]) == 2

    assert "'explode' is not one of" in capsys.readouterr().err


def test_needs_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_config"].return_value = None

    assert run(["exp", "finish"]) == 1

    assert "No .labnotes.toml here" in capsys.readouterr().err
    collaborators["control_run"].assert_not_awaited()


def test_help_lists_what_each_control_takes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run(["--help"]) == 0

    out = " ".join(capsys.readouterr().out.split())
    assert "set_concurrency a number" in out
    assert "move a run and its new place in the queue" in out
