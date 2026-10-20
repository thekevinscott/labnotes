import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.server import server

SERVER: list[str] = []


@pytest.fixture
def collaborators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, mock.MagicMock]]:
    monkeypatch.chdir(tmp_path)
    with (
        mock.patch("labnotes.server.uvicorn_main") as uvicorn_main,
        mock.patch("labnotes.server.load_config") as load_config,
        mock.patch.dict("os.environ", clear=True),
    ):
        load_config.return_value.path = Path("p/.labnotes.toml")
        yield {"uvicorn_main": uvicorn_main, "load_config": load_config}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        server.main(argv, prog_name="server")
    return exit_info.value.code


def test_serves_the_app_factory_on_localhost_by_default(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(SERVER) == 0

    kwargs = collaborators["uvicorn_main"].call_args.kwargs
    assert kwargs["app"] == "labnotes.serve_app:serve_app"
    assert kwargs["factory"] is True
    assert (kwargs["host"], kwargs["port"]) == ("127.0.0.1", 8000)


def test_passes_the_config_to_the_factory_as_an_absolute_path(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run(SERVER)

    collaborators["uvicorn_main"].assert_called_once()
    assert os.environ["LABNOTES_CONFIG"] == str(Path("p/.labnotes.toml").resolve())


def test_requires_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_config"].return_value = None

    assert run(SERVER) == 1

    assert "No .labnotes.toml here." in capsys.readouterr().err
    collaborators["uvicorn_main"].assert_not_called()


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


def test_server_help_shows_the_bind_defaults_and_uvicorn_options(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    out = " ".join(capsys.readouterr().out.split())
    assert "[default: 127.0.0.1]" in out
    assert "[default: 8000]" in out
    assert "--proxy-headers" in out
