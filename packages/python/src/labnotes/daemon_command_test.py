from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.daemon_command import daemon_command


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.daemon_command.load_config") as load_config,
        mock.patch("labnotes.daemon_command.serve_daemon") as serve_daemon,
    ):
        yield {"load_config": load_config, "serve_daemon": serve_daemon}


def run() -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        daemon_command.main([], prog_name="daemon")
    return exit_info.value.code


def test_serves_the_project(collaborators: dict[str, mock.MagicMock]) -> None:
    assert run() == 0

    collaborators["serve_daemon"].assert_called_once_with(
        collaborators["load_config"].return_value
    )


def test_needs_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_config"].return_value = None

    assert run() == 1

    assert "No .labnotes.toml here" in capsys.readouterr().err
    collaborators["serve_daemon"].assert_not_called()


def test_is_hidden() -> None:
    assert daemon_command.hidden
