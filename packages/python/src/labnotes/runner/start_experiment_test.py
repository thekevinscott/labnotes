import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.start_experiment import start_experiment


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    experiment = mock.Mock()
    with (
        mock.patch(
            "labnotes.runner.start_experiment.prepare_experiment",
            new=mock.AsyncMock(return_value=(experiment, 2, tmp_path / "runs")),
        ) as prepare_experiment,
        mock.patch(
            "labnotes.runner.start_experiment.run_experiment",
            new=mock.AsyncMock(return_value=[{"exit_code": 0}]),
        ) as run_experiment,
        mock.patch("labnotes.runner.start_experiment.hold_folder") as hold_folder,
    ):
        yield {
            "experiment": experiment,
            "prepare_experiment": prepare_experiment,
            "run_experiment": run_experiment,
            "hold_folder": hold_folder,
        }


def drive() -> mock.Mock:
    return mock.Mock(
        side_effect=lambda start, title: asyncio.run(start("report", "listen"))
    )


def test_runs_the_experiment_under_a_lock(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    config = mock.Mock()
    path = tmp_path / "other.toml"

    assert start_experiment(config, "exp", path, 5, drive()) == [{"exit_code": 0}]

    collaborators["prepare_experiment"].assert_awaited_once_with(config, "exp", path, 5)
    collaborators["hold_folder"].assert_called_once_with(tmp_path / "runs")
    collaborators["run_experiment"].assert_awaited_once_with(
        config, "exp", collaborators["experiment"], 2, "report", "listen"
    )


@pytest.mark.parametrize(("display_name", "title"), [("Study", "Study"), (None, "exp")])
def test_titles_the_run_with_the_display_name(
    collaborators: dict[str, mock.MagicMock], display_name: str | None, title: str
) -> None:
    collaborators["experiment"].name = display_name
    driver = drive()

    start_experiment(mock.Mock(), "exp", None, 1, driver)

    assert driver.call_args.args[1] == title


def test_refuses_to_run_twice(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["hold_folder"].return_value.__enter__.side_effect = BlockingIOError()

    with pytest.raises(ValueError) as error:
        start_experiment(mock.Mock(), "exp", None, 1, drive())

    assert str(error.value) == f"exp is already running ({tmp_path / 'runs'} is held)."
    collaborators["run_experiment"].assert_not_awaited()
