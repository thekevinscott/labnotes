import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.start_experiment import start_experiment


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.runner.start_experiment.runs_parent",
            return_value=tmp_path / "runs" / "exp",
        ) as runs_parent,
        mock.patch(
            "labnotes.runner.start_experiment.read_experiment_config"
        ) as read_experiment_config,
        mock.patch(
            "labnotes.runner.start_experiment.run_experiment",
            new=mock.AsyncMock(return_value=[{"exit_code": 0}]),
        ) as run_experiment,
        mock.patch("labnotes.runner.start_experiment.hold_folder") as hold_folder,
    ):
        yield {
            "runs_parent": runs_parent,
            "read_experiment_config": read_experiment_config,
            "run_experiment": run_experiment,
            "hold_folder": hold_folder,
        }


def drive() -> mock.Mock:
    return mock.Mock(
        side_effect=lambda start, title: asyncio.run(start("report", "listen"))
    )


def make_config(root: Path) -> mock.Mock:
    return mock.Mock(
        root=root,
        experiments="notes/{experiment}",
        runs="data/{experiment}/{run}",
        mode="fill",
        concurrency=3,
    )


def test_runs_the_experiment_under_a_lock(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "notes" / "exp" / "experiment.toml"
    path.parent.mkdir(parents=True)
    path.touch()
    config = make_config(tmp_path)

    assert start_experiment(config, "exp", None, 2, drive()) == [{"exit_code": 0}]

    collaborators["read_experiment_config"].assert_called_once_with(path, "fill", 3)
    collaborators["runs_parent"].assert_called_once_with(tmp_path, config.runs, "exp")
    collaborators["hold_folder"].assert_called_once_with(tmp_path / "runs" / "exp")
    assert (tmp_path / "runs" / "exp").is_dir()
    collaborators["run_experiment"].assert_awaited_once_with(
        config,
        "exp",
        collaborators["read_experiment_config"].return_value,
        2,
        "report",
        "listen",
    )


@pytest.mark.parametrize(("display_name", "title"), [("Study", "Study"), (None, "exp")])
def test_titles_the_run_with_the_display_name(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    display_name: str | None,
    title: str,
) -> None:
    path = tmp_path / "notes" / "exp" / "experiment.toml"
    path.parent.mkdir(parents=True)
    path.touch()
    collaborators["read_experiment_config"].return_value.name = display_name
    driver = drive()

    start_experiment(make_config(tmp_path), "exp", None, 1, driver)

    assert driver.call_args.args[1] == title


def test_reads_the_named_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "other.toml"
    path.touch()

    start_experiment(make_config(tmp_path), "exp", path, 1, drive())

    collaborators["read_experiment_config"].assert_called_once_with(path, "fill", 3)


def test_needs_an_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    with pytest.raises(ValueError, match="No experiment.toml for exp at "):
        start_experiment(make_config(tmp_path), "exp", None, 1, drive())

    collaborators["run_experiment"].assert_not_awaited()


def test_refuses_to_run_twice(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "experiment.toml"
    path.touch()
    collaborators["hold_folder"].return_value.__enter__.side_effect = BlockingIOError()

    with pytest.raises(ValueError) as error:
        start_experiment(make_config(tmp_path), "exp", path, 1, drive())

    assert (
        str(error.value)
        == f"exp is already running ({tmp_path / 'runs' / 'exp'} is held)."
    )

    collaborators["run_experiment"].assert_not_awaited()


def test_falls_back_to_the_experiment_concurrency(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "notes" / "exp" / "experiment.toml"
    path.parent.mkdir(parents=True)
    path.touch()
    collaborators["read_experiment_config"].return_value.concurrency = 4

    start_experiment(make_config(tmp_path), "exp", None, None, drive())

    assert collaborators["run_experiment"].await_args.args[3] == 4
