import json
import os
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main

ROWS = [{"name": "a", "study": "s1", "runs": 3}]
FOLDERS = ["--experiments-folder", "exp", "--data-folder", "data"]
ENV = ("LABNOTES_EXPERIMENTS_FOLDER", "LABNOTES_DATA_FOLDER")


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.cli.dump_experiments",
            new_callable=mock.AsyncMock,
            return_value=ROWS,
        ) as dump_experiments,
        mock.patch("labnotes.cli.uvicorn_main") as uvicorn_main,
        mock.patch.dict("os.environ", clear=True),
    ):
        yield {"dump_experiments": dump_experiments, "uvicorn_main": uvicorn_main}


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


def test_serves_the_app_factory_on_localhost_by_default(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(FOLDERS) == 0

    kwargs = collaborators["uvicorn_main"].call_args.kwargs
    assert kwargs["app"] == "labnotes.serve_app:serve_app"
    assert kwargs["factory"] is True
    assert (kwargs["host"], kwargs["port"]) == ("127.0.0.1", 8000)
    collaborators["dump_experiments"].assert_not_awaited()


def test_passes_the_folders_to_the_factory_as_absolute_paths(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run(FOLDERS)

    assert [os.environ[name] for name in ENV] == [
        str(Path("exp").resolve()),
        str(Path("data").resolve()),
    ]


@pytest.mark.parametrize(
    "flags", [["--host", "0.0.0.0", "--port", "9001"], ["-h", "0.0.0.0", "-p", "9001"]]
)
def test_serves_on_the_given_host_and_port(
    flags: list[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    run([*FOLDERS, *flags])

    kwargs = collaborators["uvicorn_main"].call_args.kwargs
    assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 9001)


def test_passes_uvicorn_options_through(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run([*FOLDERS, "--reload", "--forwarded-allow-ips", "*", "--log-level", "debug"])

    kwargs = collaborators["uvicorn_main"].call_args.kwargs
    assert kwargs["reload"] is True
    assert kwargs["forwarded_allow_ips"] == "*"
    assert kwargs["log_level"] == "debug"


@pytest.mark.parametrize("flag", ["--factory", "--app-dir"])
def test_hides_uvicorn_options_labnotes_owns(
    flag: str, collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run([*FOLDERS, flag, "x"]) == 2
    collaborators["uvicorn_main"].assert_not_called()


def test_reads_the_folders_from_the_environment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    with mock.patch.dict("os.environ", dict(zip(ENV, ["exp", "data"]))):
        assert run(["--json"]) == 0
    collaborators["dump_experiments"].assert_awaited_once_with(
        Path("exp"), Path("data")
    )


def test_prints_experiments_as_json(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run([*FOLDERS, "--json"]) == 0

    collaborators["dump_experiments"].assert_awaited_once_with(
        Path("exp"), Path("data")
    )
    assert capsys.readouterr().out == json.dumps(ROWS, indent=2) + "\n"
    collaborators["uvicorn_main"].assert_not_called()


@pytest.mark.parametrize(
    "argv", [["--experiments-folder", "exp"], ["--data-folder", "data"]]
)
def test_requires_both_folders(
    argv: list[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(argv) == 2
    collaborators["uvicorn_main"].assert_not_called()


def test_help_shows_the_bind_defaults_and_uvicorn_options(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    out = " ".join(capsys.readouterr().out.split())
    assert "[default: 127.0.0.1]" in out
    assert "[default: 8000]" in out
    assert "--kernel-idle-minutes INTEGER RANGE" in out
    assert "Stop a note's Python kernel after this long without a run." in out
    assert "--proxy-headers" in out


def test_passes_the_kernel_idle_limit_to_the_factory(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run([*FOLDERS, "--kernel-idle-minutes", "1"]) == 0

    assert os.environ["LABNOTES_KERNEL_IDLE_MINUTES"] == "1"


def test_stops_idle_kernels_after_thirty_minutes_by_default(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run(FOLDERS)

    assert os.environ["LABNOTES_KERNEL_IDLE_MINUTES"] == "30"


def test_reads_the_kernel_idle_limit_from_the_environment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    with mock.patch.dict("os.environ", {"LABNOTES_KERNEL_IDLE_MINUTES": "12"}):
        run(FOLDERS)
        assert os.environ["LABNOTES_KERNEL_IDLE_MINUTES"] == "12"


def test_rejects_a_kernel_idle_limit_under_a_minute(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run([*FOLDERS, "--kernel-idle-minutes", "0"]) == 2
    collaborators["uvicorn_main"].assert_not_called()
