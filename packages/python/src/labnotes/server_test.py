import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.server import server

SERVER = ["--experiments-folder", "exp", "--data-folder", "data"]
ENV = ("LABNOTES_EXPERIMENTS_FOLDER", "LABNOTES_DATA_FOLDER")


@pytest.fixture
def collaborators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, mock.MagicMock]]:
    monkeypatch.chdir(tmp_path)
    with (
        mock.patch("labnotes.server.load_config", return_value=None) as load_config,
        mock.patch("labnotes.server.uvicorn_main") as uvicorn_main,
        mock.patch.dict("os.environ", clear=True),
    ):
        yield {"uvicorn_main": uvicorn_main, "load_config": load_config}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        server.main(argv, prog_name="server")
    return exit_info.value.code


def served_folders(uvicorn_main: mock.MagicMock) -> list[str]:
    uvicorn_main.assert_called_once()
    return [os.environ[name] for name in ENV]


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
        assert run([]) == 0
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
    assert run(argv) == 2

    assert "--experiments-folder and --data-folder are required without a" in (
        capsys.readouterr().err
    )
    collaborators["uvicorn_main"].assert_not_called()


def test_server_help_shows_the_bind_defaults_and_uvicorn_options(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

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


def configure(load_config: mock.MagicMock) -> None:
    load_config.return_value = mock.Mock(
        experiments_folder=Path("/p/exp"), data_folder=Path("/p/data")
    )


def test_serves_the_folders_from_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    configure(collaborators["load_config"])

    assert run([]) == 0

    assert served_folders(collaborators["uvicorn_main"]) == ["/p/exp", "/p/data"]


def test_flags_override_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    configure(collaborators["load_config"])

    assert run(["--data-folder", "data"]) == 0

    assert served_folders(collaborators["uvicorn_main"]) == [
        "/p/exp",
        str(Path("data").resolve()),
    ]


def test_the_environment_overrides_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    configure(collaborators["load_config"])

    with mock.patch.dict("os.environ", {ENV[0]: "exp"}):
        assert run([]) == 0
        assert served_folders(collaborators["uvicorn_main"]) == [
            str(Path("exp").resolve()),
            "/p/data",
        ]
