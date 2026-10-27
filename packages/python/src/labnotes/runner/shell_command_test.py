from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.shell_command import shell_command


@pytest.fixture(autouse=True)
def param_args() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.runner.shell_command.param_args", return_value=["--m", "a b"]
    ) as param_args:
        yield param_args


def test_appends_the_params(param_args: mock.MagicMock) -> None:
    assert shell_command("study", Path("/r"), {"m": "a b"}) == "study --m 'a b'"
    param_args.assert_called_once_with({"m": "a b"})


def test_fills_in_the_run_folder() -> None:
    command = "study --out {run_dir} --log {run_dir}/log"

    assert shell_command(command, Path("/my runs/r1"), {}) == (
        "study --out '/my runs/r1' --log '/my runs/r1'/log --m 'a b'"
    )


def test_leaves_a_command_without_params_alone(param_args: mock.MagicMock) -> None:
    param_args.return_value = []

    assert shell_command("study ${HOME}", Path("/r"), {}) == "study ${HOME}"


def test_appends_args_after_the_params() -> None:
    assert shell_command("study", Path("/r"), {}, ["--auth", "a b"]) == (
        "study --m 'a b' --auth 'a b'"
    )
