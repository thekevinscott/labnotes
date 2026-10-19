from pathlib import Path

import pytest

from labnotes.runner.runs_parent import runs_parent


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{experiment}/runs/{run}", "/p/exp/runs"),
        ("data/{experiment}/{run}", "/p/data/exp"),
        ("{experiment}/runs/run-{run}", "/p/exp/runs"),
    ],
)
def test_finds_the_folder_holding_the_runs(template: str, expected: str) -> None:
    assert runs_parent(Path("/p"), template, "exp") == Path(expected)
