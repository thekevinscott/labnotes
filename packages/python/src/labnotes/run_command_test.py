from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.run_command import run_command


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.run_command.load_config") as load_config,
        mock.patch(
            "labnotes.run_command.stop_runs", new=mock.AsyncMock(return_value=True)
        ) as stop_runs,
    ):
        yield {"load_config": load_config, "stop_runs": stop_runs}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        run_command.main(argv, prog_name="run")
    return exit_info.value.code


@pytest.mark.parametrize(
    ("stopping", "said"), [(True, "Stopping runs.\n"), (False, "Nothing is running.\n")]
)
def test_stops_the_projects_runs(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    stopping: bool,
    said: str,
) -> None:
    collaborators["stop_runs"].return_value = stopping

    assert run(["stop"]) == 0

    collaborators["stop_runs"].assert_awaited_once_with(
        collaborators["load_config"].return_value.root
    )
    assert capsys.readouterr().out == said


def test_needs_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_config"].return_value = None

    assert run(["stop"]) == 1

    assert "No .labnotes.toml here" in capsys.readouterr().err
    collaborators["stop_runs"].assert_not_awaited()


def test_help_says_how_runs_stop(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["stop", "--help"]) == 0

    assert "SIGKILL 5 seconds later" in capsys.readouterr().out
