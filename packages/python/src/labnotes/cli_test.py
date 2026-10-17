from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main

CONFIG_TEXT = 'experiments = "/p/exp"\ndata = "/p/data"\n'

SERVER = ["server", "--experiments-folder", "exp", "--data-folder", "data"]
ENV = ("LABNOTES_EXPERIMENTS_FOLDER", "LABNOTES_DATA_FOLDER")


@pytest.fixture
def collaborators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, mock.MagicMock]]:
    monkeypatch.chdir(tmp_path)
    with (
        mock.patch(
            "labnotes.cli.context_guide", return_value="GUIDE\n"
        ) as context_guide,
        mock.patch("labnotes.server.uvicorn_main") as uvicorn_main,
        mock.patch.dict("os.environ", clear=True),
    ):
        yield {"uvicorn_main": uvicorn_main, "context_guide": context_guide}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    return exit_info.value.code


def test_version_prints_installed_version(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--version"]) == 0
    assert capsys.readouterr().out.strip().endswith(version("labnotes"))
    collaborators["uvicorn_main"].assert_not_called()


def test_prints_help_without_a_command(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run([]) == 0

    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "server" in out
    assert "context" in out
    collaborators["uvicorn_main"].assert_not_called()


def test_context_prints_the_agent_guide_without_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["context"]) == 0

    assert capsys.readouterr().out == "GUIDE\n"
    collaborators["context_guide"].assert_called_once_with(None, Path.cwd())
    collaborators["uvicorn_main"].assert_not_called()


def write_config(path: Path) -> Path:
    path.write_text(CONFIG_TEXT, encoding="utf-8")
    return path.resolve()


def test_context_names_the_config_in_the_working_folder(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    path = write_config(Path(".labnotes.toml"))

    assert run(["context"]) == 0

    config, cwd = collaborators["context_guide"].call_args.args
    assert (config.path, config.experiments_folder, config.data_folder) == (
        path,
        Path("/p/exp"),
        Path("/p/data"),
    )
    assert cwd == Path.cwd()


@pytest.mark.parametrize("command", ["server", "context"])
def test_reports_a_broken_config_on_stderr(
    command: str,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    Path(".labnotes.toml").write_text("zz = 1\n", encoding="utf-8")

    assert run([command]) == 1

    assert "unknown keys zz" in capsys.readouterr().err
    collaborators["uvicorn_main"].assert_not_called()
