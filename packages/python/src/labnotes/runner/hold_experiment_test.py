from pathlib import Path

import pytest

from labnotes.models import LabnotesConfig
from labnotes.runner.hold_experiment import hold_experiment


def config(root: Path) -> LabnotesConfig:
    return LabnotesConfig(
        root / ".labnotes.toml", root, "{experiment}", "", "{experiment}/runs/{run}"
    )


def test_refuses_a_second_hold_until_the_first_ends(tmp_path: Path) -> None:
    with hold_experiment(config(tmp_path), "exp"):
        with pytest.raises(ValueError, match="exp is already running"):
            with hold_experiment(config(tmp_path), "exp"):
                pass
        with hold_experiment(config(tmp_path), "other"):
            pass

    with hold_experiment(config(tmp_path), "exp"):
        (tmp_path / "exp" / "runs" / "r1").mkdir()

    assert [*(tmp_path / "exp" / "runs").iterdir()] == [tmp_path / "exp/runs/r1"]


def test_leaves_no_runs_folder_it_made_and_left_empty(tmp_path: Path) -> None:
    with hold_experiment(config(tmp_path), "exp"):
        assert (tmp_path / "exp" / "runs").is_dir()

    assert not (tmp_path / "exp" / "runs").exists()
    assert (tmp_path / "exp").is_dir()
