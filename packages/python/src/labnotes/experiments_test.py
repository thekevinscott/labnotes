from collections.abc import Iterator
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


def test_rejects_an_unknown_action(collaborators: dict[str, mock.MagicMock]) -> None:
    assert run(["a", "jump"]) == 2


def test_help_shows_the_default_format(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    assert "[default: table]" in capsys.readouterr().out
