import json
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main

ROWS = [{"name": "a", "study": "s1", "runs": 3}]
FOLDERS = ["--experiments-folder", "exp", "--data-folder", "data"]


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.cli.dump_experiments",
            new_callable=mock.AsyncMock,
            return_value=ROWS,
        ) as dump_experiments,
        mock.patch("labnotes.cli.create_app") as create_app,
        mock.patch("labnotes.cli.uvicorn") as uvicorn,
    ):
        yield {
            "dump_experiments": dump_experiments,
            "create_app": create_app,
            "uvicorn": uvicorn,
        }


def test_version_prints_installed_version(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == version("labnotes")
    collaborators["uvicorn"].run.assert_not_called()


def test_serves_the_app_on_localhost_by_default(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    main(FOLDERS)

    collaborators["create_app"].assert_called_once_with(Path("exp"), Path("data"))
    collaborators["uvicorn"].run.assert_called_once_with(
        collaborators["create_app"].return_value,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
    )
    assert capsys.readouterr().err == "labnotes at http://127.0.0.1:8000\n"
    collaborators["dump_experiments"].assert_not_awaited()


def test_serves_on_the_given_host_and_port(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    main([*FOLDERS, "--host", "0.0.0.0", "--port", "9001"])

    kwargs = collaborators["uvicorn"].run.call_args.kwargs
    assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 9001)


def test_prints_experiments_as_json(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    main([*FOLDERS, "--json"])

    collaborators["dump_experiments"].assert_awaited_once_with(
        Path("exp"), Path("data")
    )
    assert capsys.readouterr().out == json.dumps(ROWS, indent=2) + "\n"
    collaborators["uvicorn"].run.assert_not_called()


@pytest.mark.parametrize(
    "argv", [["--experiments-folder", "exp"], ["--data-folder", "data"]]
)
def test_requires_both_folders(
    argv: list[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 2
    collaborators["uvicorn"].run.assert_not_called()
