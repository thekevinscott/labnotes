from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main


@pytest.fixture
def collaborators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, mock.MagicMock]]:
    monkeypatch.chdir(tmp_path)
    with (
        mock.patch(
            "labnotes.cli.context_guide", return_value="GUIDE\n"
        ) as context_guide,
        mock.patch("labnotes.cli.load_config") as load_config,
    ):
        yield {"context_guide": context_guide, "load_config": load_config}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    return exit_info.value.code


def config_path(load_config: mock.MagicMock) -> Path:
    load_config.assert_called_once()
    path: Path = load_config.call_args.args[0].obj
    return path


def test_version_prints_installed_version(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--version"]) == 0
    assert capsys.readouterr().out.strip().endswith(version("labnotes"))


def test_prints_help_without_a_command(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run([]) == 0

    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "server" in out
    assert "context" in out
    collaborators["load_config"].assert_not_called()


def test_context_prints_the_agent_guide_for_the_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["context"]) == 0

    assert capsys.readouterr().out == "GUIDE\n"
    collaborators["context_guide"].assert_called_once_with(
        collaborators["load_config"].return_value, Path.cwd()
    )


def test_reads_the_config_in_the_working_folder(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(["context"]) == 0

    assert config_path(collaborators["load_config"]) == Path.cwd() / ".labnotes.toml"


@pytest.mark.parametrize("flag", ["-c", "--config"])
def test_reads_the_config_named_by_the_flag(
    flag: str, collaborators: dict[str, mock.MagicMock]
) -> None:
    Path("project.toml").write_text("", encoding="utf-8")

    assert run([flag, "project.toml", "context"]) == 0

    assert config_path(collaborators["load_config"]) == Path("project.toml")


def test_rejects_a_missing_config_named_by_the_flag(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["-c", "missing.toml", "context"]) == 2

    assert "'missing.toml' does not exist" in capsys.readouterr().err
    collaborators["load_config"].assert_not_called()


def test_rejects_a_folder_named_by_the_flag(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    Path("folder").mkdir()

    assert run(["-c", "folder", "context"]) == 2

    assert "'folder' is a directory" in capsys.readouterr().err
    collaborators["load_config"].assert_not_called()
