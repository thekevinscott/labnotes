from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.experiments import experiments


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.experiments.load_config") as load_config,
        mock.patch(
            "labnotes.experiments.experiment_rows",
            new=mock.AsyncMock(return_value=[{"name": "a"}]),
        ) as experiment_rows,
        mock.patch("labnotes.experiments.print_rows") as print_rows,
    ):
        yield {
            "load_config": load_config,
            "experiment_rows": experiment_rows,
            "print_rows": print_rows,
        }


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        experiments.main(argv, prog_name="experiments")
    return exit_info.value.code


@pytest.mark.parametrize(
    ("argv", "name", "action"),
    [([], None, None), (["a"], "a", None), (["a", "runs"], "a", "runs")],
)
def test_prints_the_rows_as_a_table(
    argv: list[str],
    name: str | None,
    action: str | None,
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(argv) == 0

    collaborators["experiment_rows"].assert_awaited_once_with(
        collaborators["load_config"].return_value, name, action
    )
    collaborators["print_rows"].assert_called_once_with([{"name": "a"}], "table")


def test_prints_json(collaborators: dict[str, mock.MagicMock]) -> None:
    assert run(["--format", "json"]) == 0

    collaborators["print_rows"].assert_called_once_with([{"name": "a"}], "json")


def test_needs_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_config"].return_value = None

    assert run([]) == 1

    assert "No .labnotes.toml here. Run labnotes init" in capsys.readouterr().err
    collaborators["experiment_rows"].assert_not_awaited()


def test_reports_an_unknown_experiment(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["experiment_rows"].return_value = None

    assert run(["zz"]) == 1

    assert "No experiment named zz." in capsys.readouterr().err
    collaborators["print_rows"].assert_not_called()


def test_reports_a_query_that_fails(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["experiment_rows"].side_effect = ValueError("a: counts broke")

    assert run(["a", "runs"]) == 1

    assert "Error: a: counts broke" in capsys.readouterr().err
    collaborators["print_rows"].assert_not_called()


def test_rejects_an_unknown_action(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["a", "jump"]) == 2

    assert "Unknown action jump. Use runs or run." in capsys.readouterr().err
    collaborators["experiment_rows"].assert_not_called()


def test_help_says_format_prints_and_exits(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    assert "Print rows and exit." in capsys.readouterr().out


@pytest.fixture
def browse() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.experiments.browse_tui") as browse_tui,
        mock.patch("labnotes.experiments.sys") as sys,
    ):
        sys.stdout.isatty.return_value = True
        sys.stderr.isatty.return_value = True
        yield {"browse_tui": browse_tui, "sys": sys}


@pytest.mark.parametrize(
    ("argv", "name"), [([], None), (["a"], "a"), (["a", "runs"], "a")]
)
def test_browses_in_a_terminal_when_format_is_unset(
    argv: list[str],
    name: str | None,
    collaborators: dict[str, mock.MagicMock],
    browse: dict[str, mock.MagicMock],
) -> None:
    assert run(argv) == 0

    browse["browse_tui"].assert_called_once_with(
        collaborators["load_config"].return_value, name
    )
    collaborators["experiment_rows"].assert_not_awaited()
    collaborators["print_rows"].assert_not_called()


@pytest.mark.parametrize("output_format", ["table", "json"])
@pytest.mark.parametrize("argv", [[], ["a"], ["a", "runs"]])
def test_prints_in_a_terminal_when_format_is_given(
    argv: list[str],
    output_format: str,
    collaborators: dict[str, mock.MagicMock],
    browse: dict[str, mock.MagicMock],
) -> None:
    assert run([*argv, "--format", output_format]) == 0

    browse["browse_tui"].assert_not_called()
    collaborators["print_rows"].assert_called_once_with([{"name": "a"}], output_format)


@pytest.mark.parametrize(("stdout", "stderr"), [(False, True), (True, False)])
@pytest.mark.parametrize("argv", [[], ["a"], ["a", "runs"]])
def test_prints_a_table_when_either_stream_is_not_a_terminal(
    argv: list[str],
    stdout: bool,
    stderr: bool,
    collaborators: dict[str, mock.MagicMock],
    browse: dict[str, mock.MagicMock],
) -> None:
    browse["sys"].stdout.isatty.return_value = stdout
    browse["sys"].stderr.isatty.return_value = stderr

    assert run(argv) == 0

    browse["browse_tui"].assert_not_called()
    collaborators["print_rows"].assert_called_once_with([{"name": "a"}], "table")


def test_reports_an_experiment_the_browser_cannot_find(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    browse: dict[str, mock.MagicMock],
) -> None:
    browse["browse_tui"].side_effect = ValueError("No experiment named zz.")

    assert run(["zz"]) == 1

    assert "No experiment named zz." in capsys.readouterr().err


@pytest.fixture
def drivers() -> Iterator[dict[str, mock.MagicMock]]:
    results = [{"exit_code": 0}, {"exit_code": 0}]
    with (
        mock.patch(
            "labnotes.experiments.run_headless", return_value=results
        ) as run_headless,
        mock.patch("labnotes.experiments.remote_start") as remote_start,
        mock.patch("labnotes.experiments.run_tui", return_value=results) as run_tui,
        mock.patch("labnotes.experiments.sys") as sys,
    ):
        sys.stdout.isatty.return_value = False
        sys.stderr.isatty.return_value = True
        yield {
            "run_headless": run_headless,
            "remote_start": remote_start,
            "run_tui": run_tui,
            "sys": sys,
        }


def test_runs_an_experiment_through_the_daemon(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--concurrency", "3"]) == 0

    drivers["remote_start"].assert_called_once_with(
        collaborators["load_config"].return_value, "a", None, 3, None
    )
    drivers["run_headless"].assert_called_once_with(
        drivers["remote_start"].return_value
    )
    drivers["run_tui"].assert_not_called()
    assert capsys.readouterr().out == "2 passed, 0 failed.\n"
    collaborators["experiment_rows"].assert_not_awaited()


def test_runs_an_experiment_from_a_named_config(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    path = tmp_path / "other.toml"
    path.touch()

    assert run(["a", "run", "-e", str(path)]) == 0

    assert drivers["remote_start"].call_args.args[1:4] == ("a", path, None)


def test_exits_zero_when_a_run_fails(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["run_headless"].return_value = [
        {"exit_code": 0},
        {"exit_code": 2},
        {"exit_code": None},
    ]

    assert run(["a", "run"]) == 0

    assert capsys.readouterr().out == "1 passed, 2 failed.\n"


def test_counts_a_retried_run_once(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["run_headless"].return_value = [
        {"run": "r1", "exit_code": 75},
        {"run": "r2", "exit_code": 1},
        {"run": "r3", "exit_code": 0, "retry_of": "r1"},
        {"run": "r4", "exit_code": 0},
        {"run": "r5", "exit_code": 75},
        {"run": "r6", "exit_code": 0, "retry_of": "r5"},
    ]

    assert run(["a", "run"]) == 0

    assert capsys.readouterr().out == "3 passed, 1 failed. 2 retried.\n"


@pytest.mark.parametrize("terminal", [True, False])
def test_reports_an_experiment_that_cannot_run(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    terminal: bool,
) -> None:
    drivers["sys"].stdout.isatty.return_value = terminal
    drivers["run_headless"].side_effect = ValueError("a is already running")
    drivers["run_tui"].side_effect = ValueError("a is already running")

    assert run(["a", "run"]) == 1

    assert "a is already running" in capsys.readouterr().err


def test_help_says_concurrency_falls_back_to_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    assert "1 if none" in capsys.readouterr().out


def test_needs_a_concurrency_of_at_least_one(
    collaborators: dict[str, mock.MagicMock], drivers: dict[str, mock.MagicMock]
) -> None:
    assert run(["a", "run", "--concurrency", "0"]) == 2

    drivers["remote_start"].assert_not_called()


@pytest.mark.parametrize("path", ["missing.toml", "."])
def test_needs_an_experiment_config_file(
    tmp_path: Path,
    path: str,
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "-e", str(tmp_path / path)]) == 2

    drivers["remote_start"].assert_not_called()


def test_prints_events_when_stderr_is_not_a_terminal(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["sys"].stdout.isatty.return_value = True
    drivers["sys"].stderr.isatty.return_value = False

    run(["a", "run"])

    drivers["run_headless"].assert_called_once()
    drivers["run_tui"].assert_not_called()


def test_shows_the_live_view_in_a_terminal(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["sys"].stdout.isatty.return_value = True

    assert run(["a", "run", "--concurrency", "3"]) == 0

    drivers["remote_start"].assert_called_once_with(
        collaborators["load_config"].return_value, "a", None, 3, None
    )
    drivers["run_tui"].assert_called_once_with(
        drivers["remote_start"].return_value, "a"
    )
    drivers["run_headless"].assert_not_called()
    assert capsys.readouterr().out == "2 passed, 0 failed.\n"


@pytest.mark.parametrize(
    ("argv", "name"), [(["new"], None), (["new", "study"], "study")]
)
def test_creates_an_experiment(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    argv: list[str],
    name: str | None,
) -> None:
    with mock.patch(
        "labnotes.experiments.create_experiment", return_value=Path("notes/study")
    ) as create_experiment:
        assert run(argv) == 0

    create_experiment.assert_called_once_with(
        collaborators["load_config"].return_value, name
    )
    assert capsys.readouterr().out == "Created notes/study/experiment.toml\n"
    collaborators["experiment_rows"].assert_not_called()


def test_reports_an_experiment_that_cannot_be_created(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch(
        "labnotes.experiments.create_experiment",
        side_effect=ValueError("study already exists"),
    ):
        assert run(["new", "study"]) == 1

    assert "study already exists" in capsys.readouterr().err


def test_sends_the_timeout_in_seconds(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--timeout", "90"]) == 0

    assert drivers["remote_start"].call_args.args[4] == 90


@pytest.mark.parametrize("given", ["0", "-5"])
def test_needs_a_timeout_over_zero(
    given: str,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--timeout", given]) == 2

    assert "is not in the range x>=1" in capsys.readouterr().err
    drivers["remote_start"].assert_not_called()


def test_help_says_runs_have_no_timeout_by_default(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    out = " ".join(capsys.readouterr().out.split())
    assert "--timeout SECONDS" in out
    assert "stop any run still going after this many seconds." in out
    assert "Unset, runs have no time limit." in out


def test_shows_memory_and_size_readably_in_a_table(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["experiment_rows"].return_value = [
        {"id": "r", "memory": 3_200_000_000, "size": None}
    ]

    assert run(["a", "runs"]) == 0

    collaborators["print_rows"].assert_called_once_with(
        [{"id": "r", "memory": "3.2 GB", "size": ""}], "table"
    )


def test_keeps_memory_and_size_in_bytes_in_json(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["experiment_rows"].return_value = [
        {"id": "r", "memory": 3_200_000_000, "size": 12}
    ]

    assert run(["a", "runs", "--format", "json"]) == 0

    collaborators["print_rows"].assert_called_once_with(mock.ANY, "json")
    [printed, _] = collaborators["print_rows"].call_args.args
    assert printed == [{"id": "r", "memory": 3_200_000_000, "size": 12}]
    assert [type(printed[0][key]) for key in ("memory", "size")] == [int, int]
