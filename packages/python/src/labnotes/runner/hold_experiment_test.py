from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.hold_experiment import hold_experiment


@pytest.fixture
def config(tmp_path: Path) -> Iterator[mock.Mock]:
    config = mock.Mock(root=tmp_path, runs="{experiment}/runs/{run}")
    with mock.patch(
        "labnotes.runner.hold_experiment.runs_parent",
        side_effect=lambda root, runs, name: root / name / "runs",
    ) as parent:
        yield config
    parent.assert_called_with(tmp_path, "{experiment}/runs/{run}", mock.ANY)


def test_refuses_a_second_hold_until_the_first_ends(
    config: mock.Mock, tmp_path: Path
) -> None:
    with hold_experiment(config, "exp"):
        with pytest.raises(ValueError, match="exp is already running"):
            with hold_experiment(config, "exp"):
                pass
        with hold_experiment(config, "other"):
            pass

    with hold_experiment(config, "exp"):
        (tmp_path / "exp" / "runs" / "r1").mkdir()

    assert [*(tmp_path / "exp" / "runs").iterdir()] == [tmp_path / "exp/runs/r1"]


def test_leaves_no_runs_folder_it_made_and_left_empty(
    config: mock.Mock, tmp_path: Path
) -> None:
    with hold_experiment(config, "exp"):
        assert (tmp_path / "exp" / "runs").is_dir()

    assert not (tmp_path / "exp" / "runs").exists()
    assert (tmp_path / "exp").is_dir()


def test_a_held_experiment_is_refused_without_waiting(config: mock.Mock) -> None:
    with mock.patch("labnotes.runner.hold_experiment.fcntl") as fcntl:
        fcntl.LOCK_EX, fcntl.LOCK_NB = 2, 4
        fcntl.flock.side_effect = BlockingIOError
        with pytest.raises(ValueError, match="exp is already running"):
            with hold_experiment(config, "exp"):
                pass
    assert fcntl.flock.call_args.args[1] == 2 | 4
