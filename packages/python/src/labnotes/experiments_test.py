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


def test_help_shows_the_default_format(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    assert "[default: table]" in capsys.readouterr().out


@pytest.fixture
def drivers() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.experiments.run_headless") as run_headless,
        mock.patch("labnotes.experiments.run_tui") as run_tui,
        mock.patch("labnotes.experiments.sys") as sys,
    ):
        sys.stdout.isatty.return_value = False
        sys.stderr.isatty.return_value = True
        yield {"run_headless": run_headless, "run_tui": run_tui, "sys": sys}


@pytest.fixture
def start_experiment(drivers: dict[str, mock.MagicMock]) -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.experiments.start_experiment",
        return_value=[{"exit_code": 0}, {"exit_code": 0}],
    ) as start_experiment:
        yield start_experiment


def test_runs_an_experiment(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    assert run(["a", "run", "--concurrency", "3"]) == 0

    start_experiment.assert_called_once_with(
        collaborators["load_config"].return_value, "a", None, 3, mock.ANY
    )
    assert capsys.readouterr().out == "2 passed, 0 failed.\n"
    collaborators["experiment_rows"].assert_not_awaited()


def test_runs_an_experiment_from_a_named_config(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    path = tmp_path / "other.toml"
    path.touch()

    assert run(["a", "run", "-e", str(path)]) == 0

    assert start_experiment.call_args.args[1:4] == ("a", path, None)


def test_exits_zero_when_a_run_fails(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    start_experiment.return_value = [
        {"exit_code": 0},
        {"exit_code": 2},
        {"exit_code": None},
    ]

    assert run(["a", "run"]) == 0

    assert capsys.readouterr().out == "1 passed, 2 failed.\n"


def test_reports_an_experiment_that_cannot_run(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    start_experiment.side_effect = ValueError("a is already running")

    assert run(["a", "run"]) == 1

    assert "a is already running" in capsys.readouterr().err


def test_help_says_concurrency_falls_back_to_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    assert "1 if none" in capsys.readouterr().out


def test_needs_a_concurrency_of_at_least_one(
    collaborators: dict[str, mock.MagicMock], start_experiment: mock.MagicMock
) -> None:
    assert run(["a", "run", "--concurrency", "0"]) == 2

    start_experiment.assert_not_called()


@pytest.mark.parametrize("path", ["missing.toml", "."])
def test_needs_an_experiment_config_file(
    tmp_path: Path,
    path: str,
    collaborators: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    assert run(["a", "run", "-e", str(tmp_path / path)]) == 2

    start_experiment.assert_not_called()


def assert_headless(
    start_experiment: mock.MagicMock, drivers: dict[str, mock.MagicMock]
) -> None:
    drive = start_experiment.call_args.args[4]
    assert drive("start", "title") is drivers["run_headless"].return_value
    drivers["run_headless"].assert_called_once_with("start")


def test_prints_events_when_not_in_a_terminal(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    run(["a", "run"])

    assert_headless(start_experiment, drivers)


def test_prints_events_when_stderr_is_not_a_terminal(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    drivers["sys"].stdout.isatty.return_value = True
    drivers["sys"].stderr.isatty.return_value = False

    run(["a", "run"])

    assert_headless(start_experiment, drivers)


def test_shows_the_live_view_in_a_terminal(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    start_experiment: mock.MagicMock,
) -> None:
    drivers["sys"].stdout.isatty.return_value = True

    run(["a", "run"])

    assert start_experiment.call_args.args[4] is drivers["run_tui"]


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
