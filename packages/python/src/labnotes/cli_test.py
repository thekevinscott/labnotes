import json
import os
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main
from labnotes.models import LabnotesConfig

ROWS = [{"name": "a", "study": "s1", "runs": 3}]
FOLDERS = ["--experiments-folder", "exp", "--data-folder", "data"]
ENV = ("LABNOTES_EXPERIMENTS_FOLDER", "LABNOTES_DATA_FOLDER")
CONFIG = LabnotesConfig(Path("/p/.labnotes.toml"), Path("/p/exp"), Path("/p/data"))


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.cli.dump_experiments",
            new_callable=mock.AsyncMock,
            return_value=ROWS,
        ) as dump_experiments,
        mock.patch(
            "labnotes.cli.query_experiment",
            new_callable=mock.AsyncMock,
            return_value=ROWS,
        ) as query_experiment,
        mock.patch(
            "labnotes.cli.context_guide", return_value="GUIDE\n"
        ) as context_guide,
        mock.patch("labnotes.cli.find_config", return_value=None) as find_config,
        mock.patch("labnotes.cli.uvicorn_main") as uvicorn_main,
        mock.patch.dict("os.environ", clear=True),
    ):
        yield {
            "dump_experiments": dump_experiments,
            "query_experiment": query_experiment,
            "uvicorn_main": uvicorn_main,
            "context_guide": context_guide,
            "find_config": find_config,
        }


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
    assert "[default: 30;" in out
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


def test_context_prints_the_agent_guide_without_folders(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["".join(["con", "text"])]) == 0

    assert capsys.readouterr().out == "GUIDE\n"
    collaborators["context_guide"].assert_called_once_with(None, Path.cwd())
    collaborators["query_experiment"].assert_not_awaited()
    collaborators["uvicorn_main"].assert_not_called()


def test_prints_what_has_run_for_an_experiment(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["a", *FOLDERS]) == 0

    collaborators["query_experiment"].assert_awaited_once_with(
        Path("exp"), Path("data"), "a", None
    )
    assert capsys.readouterr().out == json.dumps(ROWS, indent=2) + "\n"
    collaborators["uvicorn_main"].assert_not_called()


def test_queries_an_experiments_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "SELECT 1", *FOLDERS]) == 0

    collaborators["query_experiment"].assert_awaited_once_with(
        Path("exp"), Path("data"), "a", "SELECT 1"
    )


def test_queries_an_experiment_named_context_when_given_sql(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(["context", "SELECT 1", *FOLDERS]) == 0

    collaborators["query_experiment"].assert_awaited_once_with(
        Path("exp"), Path("data"), "context", "SELECT 1"
    )


@pytest.mark.parametrize(
    "error", [LookupError("no experiment named 'a'"), RuntimeError("no such column")]
)
def test_reports_a_failed_query_on_stderr(
    error: Exception,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["query_experiment"].side_effect = error

    assert run(["a", "SELECT 1", *FOLDERS]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"Error: {error}" in captured.err


def test_an_experiment_needs_both_folders(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["a", "--data-folder", "data"]) == 2

    assert "--experiments-folder and --data-folder are required without a" in (
        capsys.readouterr().err
    )
    collaborators["query_experiment"].assert_not_awaited()


def test_looks_for_the_config_from_the_working_folder(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    run(FOLDERS)

    collaborators["find_config"].assert_called_once_with(Path.cwd())


def test_context_names_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["find_config"].return_value = CONFIG

    assert run(["".join(["con", "text"])]) == 0

    collaborators["context_guide"].assert_called_once_with(CONFIG, Path.cwd())


def test_reads_the_folders_from_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["find_config"].return_value = CONFIG

    assert run(["a"]) == 0

    collaborators["query_experiment"].assert_awaited_once_with(
        Path("/p/exp"), Path("/p/data"), "a", None
    )


def test_flags_override_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["find_config"].return_value = CONFIG

    assert run(["--json", "--data-folder", "data"]) == 0

    collaborators["dump_experiments"].assert_awaited_once_with(
        Path("/p/exp"), Path("data")
    )


def test_the_environment_overrides_the_config(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["find_config"].return_value = CONFIG

    with mock.patch.dict("os.environ", {ENV[0]: "exp"}):
        assert run(["--json"]) == 0

    collaborators["dump_experiments"].assert_awaited_once_with(
        Path("exp"), Path("/p/data")
    )


def test_reports_a_broken_config_on_stderr(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["find_config"].side_effect = ValueError("bad .labnotes.toml")

    assert run(["--json"]) == 1

    assert "Error: bad .labnotes.toml" in capsys.readouterr().err
    collaborators["dump_experiments"].assert_not_awaited()
