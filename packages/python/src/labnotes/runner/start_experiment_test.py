from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.start_experiment import start_experiment


class FakeTimeout(Exception):
    pass


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.runner.start_experiment.lock_path",
            return_value=tmp_path / "runs" / "exp" / ".labnotes.lock",
        ) as lock_path,
        mock.patch(
            "labnotes.runner.start_experiment.read_experiment_config"
        ) as read_experiment_config,
        mock.patch(
            "labnotes.runner.start_experiment.run_experiment",
            new=mock.AsyncMock(return_value=[{"exit_code": 0}]),
        ) as run_experiment,
        mock.patch("labnotes.runner.start_experiment.FileLock") as file_lock,
        mock.patch("labnotes.runner.start_experiment.Timeout", FakeTimeout),
    ):
        yield {
            "lock_path": lock_path,
            "read_experiment_config": read_experiment_config,
            "run_experiment": run_experiment,
            "FileLock": file_lock,
        }


def make_config(root: Path) -> mock.Mock:
    return mock.Mock(
        root=root, experiments="notes/{experiment}", runs="data/{experiment}/{run}"
    )


def test_runs_the_experiment_under_a_lock(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "notes" / "exp" / "experiment.toml"
    path.parent.mkdir(parents=True)
    path.touch()
    config = make_config(tmp_path)
    report = mock.Mock()

    assert start_experiment(config, "exp", None, 2, report) == [{"exit_code": 0}]

    collaborators["read_experiment_config"].assert_called_once_with(path)
    collaborators["lock_path"].assert_called_once_with(tmp_path, config.runs, "exp")
    collaborators["FileLock"].assert_called_once_with(
        tmp_path / "runs" / "exp" / ".labnotes.lock", blocking=False
    )
    assert (tmp_path / "runs" / "exp").is_dir()
    collaborators["run_experiment"].assert_awaited_once_with(
        config, "exp", collaborators["read_experiment_config"].return_value, 2, report
    )


def test_reads_the_named_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "other.toml"
    path.touch()

    start_experiment(make_config(tmp_path), "exp", path, 1, mock.Mock())

    collaborators["read_experiment_config"].assert_called_once_with(path)


def test_needs_an_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    with pytest.raises(ValueError, match="No experiment.toml for exp at "):
        start_experiment(make_config(tmp_path), "exp", None, 1, mock.Mock())

    collaborators["run_experiment"].assert_not_awaited()


def test_refuses_to_run_twice(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "experiment.toml"
    path.touch()
    collaborators["FileLock"].return_value.__enter__.side_effect = FakeTimeout()

    with pytest.raises(ValueError, match="exp is already running"):
        start_experiment(make_config(tmp_path), "exp", path, 1, mock.Mock())

    collaborators["run_experiment"].assert_not_awaited()
