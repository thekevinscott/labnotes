import os
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
        mock.patch("labnotes.cli.uvicorn_main") as uvicorn_main,
        mock.patch.dict("os.environ", clear=True),
    ):
        yield {"uvicorn_main": uvicorn_main, "context_guide": context_guide}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    return exit_info.value.code


def served_folders(uvicorn_main: mock.MagicMock) -> list[str]:
    uvicorn_main.assert_called_once()
    return [os.environ[name] for name in ENV]


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


def test_serves_the_app_factory_on_localhost_by_default(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(SERVER) == 0

    kwargs = collaborators["uvicorn_main"].call_args.kwargs
    assert kwargs["app"] == "labnotes.serve_app:serve_app"
    assert kwargs["factory"] is True
    assert (kwargs["host"], kwargs["port"]) == ("127.0.0.1", 8000)


def test_passes_the_folders_to_the_factory_as_absolute_paths(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run(SERVER)

    assert served_folders(collaborators["uvicorn_main"]) == [
        str(Path("exp").resolve()),
        str(Path("data").resolve()),
    ]


@pytest.mark.parametrize(
    "flags", [["--host", "0.0.0.0", "--port", "9001"], ["-h", "0.0.0.0", "-p", "9001"]]
)
def test_serves_on_the_given_host_and_port(
    flags: list[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    run([*SERVER, *flags])

    kwargs = collaborators["uvicorn_main"].call_args.kwargs
    assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 9001)


def test_passes_uvicorn_options_through(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run([*SERVER, "--reload", "--forwarded-allow-ips", "*", "--log-level", "debug"])

    kwargs = collaborators["uvicorn_main"].call_args.kwargs
    assert kwargs["reload"] is True
    assert kwargs["forwarded_allow_ips"] == "*"
    assert kwargs["log_level"] == "debug"


@pytest.mark.parametrize("flag", ["--factory", "--app-dir"])
def test_hides_uvicorn_options_labnotes_owns(
    flag: str, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run([*SERVER, flag, "x"]) == 2
    collaborators["uvicorn_main"].assert_not_called()


def test_reads_the_folders_from_the_environment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    with mock.patch.dict("os.environ", dict(zip(ENV, ["exp", "data"], strict=True))):
        assert run(["server"]) == 0
        assert served_folders(collaborators["uvicorn_main"]) == [
            str(Path("exp").resolve()),
            str(Path("data").resolve()),
        ]


@pytest.mark.parametrize(
    "argv", [["--experiments-folder", "exp"], ["--data-folder", "data"]]
)
def test_requires_both_folders(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(["server", *argv]) == 2

    assert "--experiments-folder and --data-folder are required without a" in (
        capsys.readouterr().err
    )
    collaborators["uvicorn_main"].assert_not_called()


def test_server_help_shows_the_bind_defaults_and_uvicorn_options(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["server", "--help"]) == 0

    out = " ".join(capsys.readouterr().out.split())
    assert "[default: 127.0.0.1]" in out
    assert "[default: 8000]" in out
    assert "--kernel-idle-minutes INTEGER RANGE" in out
    assert "[default: 30;" in out
    assert "Stop a note's Python kernel after this long without a run." in out
    assert "--proxy-headers" in out


def test_passes_the_kernel_idle_limit_to_the_factory(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run([*SERVER, "--kernel-idle-minutes", "1"]) == 0

    assert os.environ["LABNOTES_KERNEL_IDLE_MINUTES"] == "1"


def test_stops_idle_kernels_after_thirty_minutes_by_default(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run(SERVER)

    assert os.environ["LABNOTES_KERNEL_IDLE_MINUTES"] == "30"


def test_reads_the_kernel_idle_limit_from_the_environment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    with mock.patch.dict("os.environ", {"LABNOTES_KERNEL_IDLE_MINUTES": "12"}):
        run(SERVER)
        assert os.environ["LABNOTES_KERNEL_IDLE_MINUTES"] == "12"


def test_rejects_a_kernel_idle_limit_under_a_minute(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run([*SERVER, "--kernel-idle-minutes", "0"]) == 2
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


def test_ignores_a_config_in_a_parent_folder(
    collaborators: dict[str, mock.MagicMock], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(Path(".labnotes.toml"))
    Path("sub").mkdir()
    monkeypatch.chdir("sub")

    assert run(["server"]) == 2
    collaborators["uvicorn_main"].assert_not_called()


def test_serves_the_folders_from_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    write_config(Path(".labnotes.toml"))

    assert run(["server"]) == 0

    assert served_folders(collaborators["uvicorn_main"]) == ["/p/exp", "/p/data"]


@pytest.mark.parametrize("flag", ["-c", "--config"])
def test_reads_the_config_named_by_the_flag(
    flag: str, collaborators: dict[str, mock.MagicMock]
) -> None:
    Path("elsewhere").mkdir()
    write_config(Path("elsewhere/project.toml"))

    assert run([flag, "elsewhere/project.toml", "server"]) == 0

    assert served_folders(collaborators["uvicorn_main"]) == ["/p/exp", "/p/data"]


def test_rejects_a_missing_config_named_by_the_flag(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["-c", "missing.toml", "server"]) == 2

    assert "'missing.toml' does not exist" in capsys.readouterr().err
    collaborators["uvicorn_main"].assert_not_called()


def test_rejects_a_folder_named_by_the_flag(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    Path("folder").mkdir()

    assert run(["-c", "folder", "server"]) == 2

    assert "'folder' is a directory" in capsys.readouterr().err
    collaborators["uvicorn_main"].assert_not_called()


def test_flags_override_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    write_config(Path(".labnotes.toml"))

    assert run(["server", "--data-folder", "data"]) == 0

    assert served_folders(collaborators["uvicorn_main"]) == [
        "/p/exp",
        str(Path("data").resolve()),
    ]


def test_the_environment_overrides_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    write_config(Path(".labnotes.toml"))

    with mock.patch.dict("os.environ", {ENV[0]: "exp"}):
        assert run(["server"]) == 0
        assert served_folders(collaborators["uvicorn_main"]) == [
            str(Path("exp").resolve()),
            "/p/data",
        ]


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
