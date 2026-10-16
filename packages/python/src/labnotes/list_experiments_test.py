import asyncio
import json
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.list_experiments import list_experiments


@pytest.fixture
def study_progress() -> Iterator[mock.AsyncMock]:
    with (
        mock.patch(
            "labnotes.list_experiments.run_columns",
            new_callable=mock.AsyncMock,
            return_value=["run_id", "x"],
        ),
        mock.patch(
            "labnotes.list_experiments.study_progress",
            new_callable=mock.AsyncMock,
            return_value={"runs": 5, "filled": 4},
        ) as patched,
    ):
        yield patched


def test_lists_each_experiment_with_its_design_summary_and_progress(
    study_progress: mock.AsyncMock,
) -> None:
    design = {"study": "s1", "runs_per_cell": 2, "varies": {"x": [1, 2]}}
    experiments = mock.Mock()
    experiments.query = mock.AsyncMock(
        return_value=[
            {"name": "a", "study": "s1", "design": json.dumps(design)},
            {"name": "b", "study": None, "design": "{}"},
        ]
    )
    runs = mock.Mock()

    [a, b] = asyncio.run(list_experiments(experiments, runs))

    assert (a["name"], a["study"], a["target"], a["runs"], a["filled"]) == (
        "a",
        "s1",
        4,
        5,
        4,
    )
    assert (b["name"], b["study"]) == ("b", None)
    first, second = study_progress.await_args_list
    assert first.args[0] is runs
    assert first.args[1] == "s1"
    assert first.args[2]["target"] == 4
    assert second.args[1] is None
    assert first.args[3] == ["run_id", "x"]
