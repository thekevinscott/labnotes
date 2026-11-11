from pathlib import Path

import pytest

from labnotes.tables.runs_folder import runs_folder

ROOT = Path("/p/project")


@pytest.mark.parametrize(
    ("template", "folder"),
    [
        ("{experiment}/runs/{run}", "alpha/runs"),
        ("runs/{run}", "runs"),
        ("results/{experiment}/{run}", "results/alpha"),
        ("runs/{run}/{experiment}", "runs"),
        ("out/*/{experiment}/{run}", "out"),
        ("{run}", ""),
        ("plain/runs", "plain/runs"),
    ],
)
def test_stops_at_the_first_part_that_is_not_literal(
    template: str, folder: str
) -> None:
    assert runs_folder(ROOT, template, "alpha") == ROOT / folder
