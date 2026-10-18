import asyncio
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.study_progress import study_progress

SUMMARY: dict[str, object] = {
    "varies": {"x": [1, 2]},
    "completed_run": "exit_code = 0",
    "runs_per_cell": 2,
}


@pytest.fixture
def count_runs() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.study_progress.count_runs",
        new_callable=mock.AsyncMock,
        side_effect=[
            [{"runs": 6, "completed": 5}],
            [{"x": 1, "runs": 6, "completed": 5}],
        ],
    ) as patched:
        yield patched


def test_caps_each_cell_at_its_target_when_filling(count_runs: mock.AsyncMock) -> None:
    runs = mock.Mock()

    progress = asyncio.run(study_progress(runs, "s", SUMMARY, ["study", "x"]))

    assert (progress["runs"], progress["completed"], progress["filled"]) == (6, 5, 2)
    assert progress["cells"] == [
        {"values": {"x": 1}, "runs": 6, "completed": 5},
        {"values": {"x": 2}, "runs": 0, "completed": 0},
    ]
    count_runs.assert_awaited_with(
        runs, "(SELECT * FROM runs WHERE study = 's')", "exit_code = 0", group_by=["x"]
    )


def test_skips_the_grid_when_runs_lack_a_varies_column(
    count_runs: mock.AsyncMock,
) -> None:
    progress = asyncio.run(study_progress(mock.Mock(), "s", SUMMARY, ["study"]))

    assert progress["missing_columns"] == ["x"]
    assert (progress["runs"], progress["filled"], progress["cells"]) == (6, None, [])
    assert count_runs.await_count == 1


def test_leaves_filled_unset_without_runs_per_cell(count_runs: mock.AsyncMock) -> None:
    summary = {**SUMMARY, "runs_per_cell": None}

    progress = asyncio.run(study_progress(mock.Mock(), "s", summary, ["x"]))

    assert progress["filled"] is None
    assert len(progress["cells"]) == 2  # type: ignore[arg-type]


def test_reports_nothing_for_an_experiment_without_a_study(
    count_runs: mock.AsyncMock,
) -> None:
    progress = asyncio.run(study_progress(mock.Mock(), None, SUMMARY, ["x"]))

    assert (progress["runs"], progress["completed"], progress["cells"]) == (0, 0, [])
    count_runs.assert_not_awaited()
