from pathlib import Path

import pytest

from labnotes.runner.lock_path import lock_path


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{experiment}/runs/{run}", "/p/exp/runs/.labnotes.lock"),
        ("data/{experiment}/{run}", "/p/data/exp/.labnotes.lock"),
        ("{experiment}/runs/run-{run}", "/p/exp/runs/.labnotes.lock"),
    ],
)
def test_locks_the_folder_holding_the_runs(template: str, expected: str) -> None:
    assert lock_path(Path("/p"), template, "exp") == Path(expected)
