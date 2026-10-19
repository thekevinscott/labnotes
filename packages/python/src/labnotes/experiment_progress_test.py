import asyncio
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.experiment_progress import experiment_progress

SUMMARY: dict[str, object] = {
    "varies": {"x": [1, 2]},
    "completed_run": "exit_code = 0",
    "runs_per_cell": 2,
    "target": 4,
}


@pytest.fixture
def count_runs() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.experiment_progress.count_runs",
        new_callable=mock.AsyncMock,
        side_effect=[
            [{"runs": 6, "completed": 5}],
            [{"x": 1, "runs": 6, "completed": 5}],
        ],
    ) as patched:
        yield patched


def test_caps_each_cell_at_its_target_when_filling(count_runs: mock.AsyncMock) -> None:
    tables = mock.Mock()

    progress = asyncio.run(experiment_progress(tables, "(source)", SUMMARY))

    assert (progress["runs"], progress["completed"], progress["filled"]) == (6, 5, 2)
    assert progress["cells"] == [
        {"values": {"x": 1}, "runs": 6, "completed": 5},
        {"values": {"x": 2}, "runs": 0, "completed": 0},
    ]
    assert count_runs.await_args_list == [
        mock.call(tables, "(source)", "exit_code = 0"),
        mock.call(tables, "(source)", "exit_code = 0", group_by=["x"]),
    ]


def test_counts_only_totals_without_a_config(count_runs: mock.AsyncMock) -> None:
    summary = {**SUMMARY, "runs_per_cell": None}

    progress = asyncio.run(experiment_progress(mock.Mock(), "(source)", summary))

    assert (progress["runs"], progress["filled"], progress["cells"]) == (6, None, [])
    assert count_runs.await_count == 1


def test_counts_cells_without_filling_an_adhoc_grid(count_runs: mock.AsyncMock) -> None:
    summary = {**SUMMARY, "target": None}

    progress = asyncio.run(experiment_progress(mock.Mock(), "(source)", summary))

    assert progress["filled"] is None
    assert [cell["completed"] for cell in progress["cells"]] == [5, 0]  # type: ignore[attr-defined]
